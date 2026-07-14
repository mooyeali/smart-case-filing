import json
import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.run_manager import AgentRunManager, make_file_id


class AgentRunManagerTest(unittest.TestCase):
    def test_creates_run_directory_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AgentRunManager(Path(tmp), run_id="run-1")
            manager.ensure()

            self.assertTrue((Path(tmp) / "run-1" / "manifest.json").exists())
            self.assertTrue((Path(tmp) / "run-1" / "traces").is_dir())
            self.assertTrue((Path(tmp) / "run-1" / "reviews").is_dir())
            self.assertTrue((Path(tmp) / "run-1" / "outputs").is_dir())
            manifest = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("run-1", manifest["run_id"])
            self.assertEqual([], manifest["files"])

    def test_allocates_stable_per_file_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AgentRunManager(Path(tmp), run_id="run-1")
            paths = manager.paths_for("cases/sample.txt")

            self.assertEqual(make_file_id("cases/sample.txt"), paths["file_id"])
            self.assertEqual(Path(tmp) / "run-1" / "traces" / f"{paths['file_id']}.trace.jsonl", paths["trace"])
            self.assertEqual(Path(tmp) / "run-1" / "reviews" / f"{paths['file_id']}.review.json", paths["review"])
            self.assertEqual(Path(tmp) / "run-1" / "outputs" / f"{paths['file_id']}.json", paths["output"])

    def test_can_use_external_reviews_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            review_dir = Path(tmp) / "custom-reviews"
            manager = AgentRunManager(Path(tmp), run_id="run-1", reviews_dir=review_dir)
            paths = manager.paths_for("cases/sample.txt")

            self.assertEqual(review_dir / f"{paths['file_id']}.review.json", paths["review"])
            index_path = manager.write_review_index()
            self.assertEqual(review_dir / "index.json", index_path)

    def test_records_file_and_updates_status_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AgentRunManager(Path(tmp), run_id="run-1")
            manager.record_file("a.txt", {
                "agent_state": "COMPLETED",
                "confidence": "high",
            })
            manager.record_file("b.txt", {
                "agent_state": "NEEDS_REVIEW",
                "confidence": "low",
            })
            manager.record_file("c.txt", {
                "agent_state": "FAILED",
                "error": "model unavailable",
            })

            manifest = manager.load_manifest()
            self.assertEqual(3, len(manifest["files"]))
            self.assertEqual({
                "COMPLETED": 1,
                "NEEDS_REVIEW": 1,
                "FAILED": 1,
            }, manifest["status_counts"])
            failed = [item for item in manifest["files"] if item["agent_state"] == "FAILED"][0]
            self.assertEqual("model unavailable", failed["error"])

    def test_summary_returns_manifest_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AgentRunManager(Path(tmp), run_id="run-1")
            manager.record_file("a.txt", {"agent_state": "COMPLETED"})

            summary = manager.summary()

            self.assertEqual("run-1", summary["run_id"])
            self.assertEqual(str(Path(tmp) / "run-1" / "manifest.json"), summary["manifest"])
            self.assertEqual(1, summary["file_count"])

    def test_writes_review_index_for_reviewable_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AgentRunManager(Path(tmp), run_id="run-1")
            manager.record_file("ok.txt", {
                "agent_state": "COMPLETED",
                "confidence": "high",
            })
            manager.record_file("review.txt", {
                "agent_state": "NEEDS_REVIEW",
                "confidence": "low",
                "reasoning": "ambiguous",
            })
            manager.record_file("failed.txt", {
                "agent_state": "FAILED",
                "error": "Authorization: Bearer sk-1234567890abcdef",
            })

            index_path = manager.write_review_index()

            raw = index_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self.assertEqual(2, data["review_count"])
            self.assertEqual({"NEEDS_REVIEW", "FAILED"}, {item["agent_state"] for item in data["items"]})
            self.assertNotIn("sk-1234567890abcdef", raw)

    def test_records_review_decision_and_updates_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AgentRunManager(Path(tmp), run_id="run-1")
            paths = manager.paths_for("review.txt")
            manager.record_file("review.txt", {
                "agent_state": "NEEDS_REVIEW",
                "confidence": "low",
            }, paths)

            result = manager.record_decision({
                "file_id": paths["file_id"],
                "file_path": "review.txt",
                "decision": "approved",
                "reviewer": "reviewer-a",
                "notes": "Authorization: Bearer sk-1234567890abcdef",
            })

            self.assertEqual("approved", result["decision"])
            decision_path = Path(result["decision_path"])
            self.assertTrue(decision_path.exists())
            self.assertNotIn("sk-1234567890abcdef", decision_path.read_text(encoding="utf-8"))
            manifest = manager.load_manifest()
            item = manifest["files"][0]
            self.assertEqual("approved", item["decision"])
            self.assertEqual(str(decision_path), item["decision_path"])
            self.assertIn("reviewed_at", item)


if __name__ == "__main__":
    unittest.main()
