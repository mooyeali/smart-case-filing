import json
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_directory_predictor as fdp
from smart_case_filing.agent.audit import audit_run


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class AgentAuditTest(unittest.TestCase):
    def make_run(self, tmp_path):
        run_dir = tmp_path / "run-1"
        traces = run_dir / "traces"
        outputs = run_dir / "outputs"
        reviews = run_dir / "reviews"
        decisions = run_dir / "decisions"
        for path in (traces, outputs, reviews, decisions):
            path.mkdir(parents=True, exist_ok=True)

        files = [
            {
                "file_id": "ok",
                "file_path": "ok.txt",
                "agent_state": "COMPLETED",
                "confidence": "high",
                "trace": str(traces / "ok.trace.jsonl"),
                "review": "",
                "output": str(outputs / "ok.json"),
                "error": "",
            },
            {
                "file_id": "review",
                "file_path": "review.txt",
                "agent_state": "NEEDS_REVIEW",
                "confidence": "low",
                "trace": str(traces / "review.trace.jsonl"),
                "review": str(reviews / "review.review.json"),
                "output": str(outputs / "review.json"),
                "error": "",
                "decision": "approved",
                "decision_path": str(decisions / "review.decision.json"),
            },
            {
                "file_id": "failed",
                "file_path": "failed.txt",
                "agent_state": "FAILED",
                "confidence": "",
                "trace": str(traces / "failed.trace.jsonl"),
                "review": str(reviews / "failed.review.json"),
                "output": str(outputs / "failed.json"),
                "error": "no catalog candidates",
            },
        ]
        for item in files:
            Path(item["trace"]).write_text("{}", encoding="utf-8")
            write_json(Path(item["output"]), {"agent_state": item["agent_state"]})
            if item.get("review"):
                write_json(Path(item["review"]), {"agent_state": item["agent_state"]})
            if item.get("decision_path"):
                write_json(Path(item["decision_path"]), {"decision": item["decision"]})
        write_json(reviews / "index.json", {
            "items": [
                {"file_id": "review"},
                {"file_id": "failed"},
            ]
        })
        write_json(run_dir / "manifest.json", {
            "run_id": "run-1",
            "status_counts": {
                "COMPLETED": 1,
                "NEEDS_REVIEW": 1,
                "FAILED": 1,
            },
            "files": files,
        })
        return run_dir

    def test_audits_complete_run_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.make_run(Path(tmp))

            result = audit_run(run_dir)

            self.assertTrue(result["valid"])
            self.assertEqual("run-1", result["run_id"])
            self.assertEqual(3, result["file_count"])
            self.assertEqual(2, result["review_count"])
            self.assertEqual(1, result["decision_count"])
            self.assertEqual([], result["issues"])

    def test_reports_missing_artifacts_and_review_index_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.make_run(Path(tmp))
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            Path(manifest["files"][0]["trace"]).unlink()
            index_path = Path(manifest["files"][1]["review"]).parent / "index.json"
            write_json(index_path, {"items": [{"file_id": "review"}]})

            result = audit_run(run_dir / "manifest.json")

            self.assertFalse(result["valid"])
            messages = [issue["message"] for issue in result["issues"]]
            self.assertTrue(any("trace path does not exist" in message for message in messages))
            self.assertTrue(any("review index does not include" in message for message in messages))

    def test_missing_manifest_returns_invalid_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = audit_run(Path(tmp) / "missing")

            self.assertFalse(result["valid"])
            self.assertIn("manifest does not exist", result["issues"][0]["message"])

    def test_cli_validate_run_without_input_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_file = Path(tmp) / "audit.json"
            log_file = Path(tmp) / "audit.log"
            with patch.object(sys, "argv", [
                "file_directory_predictor.py",
                "--agent",
                "--agent-validate-run", str(Path(tmp) / "missing"),
                "--output", str(output_file),
                "--log", str(log_file),
            ]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                fdp.main()

            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertFalse(data["valid"])
            self.assertIn("manifest does not exist", data["issues"][0]["message"])


if __name__ == "__main__":
    unittest.main()
