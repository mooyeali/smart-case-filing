import json
import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.filing import (
    build_filing_plan,
    sanitize_path_part,
    write_filing_plan,
)


def write_output(path: Path, source: Path, state="COMPLETED", confidence="high", **overrides):
    payload = {
        "file_path": str(source),
        "agent_state": state,
        "state": state,
        "confidence": confidence,
        "predicted_case_type": "民事/一审案件",
        "predicted_volume": "正卷",
        "predicted_second_level_directory": "起诉状及相关材料",
        "predicted_material_category": "民事起诉状",
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


class AgentFilingPlanTest(unittest.TestCase):
    def test_sanitize_path_part_removes_unsafe_characters(self):
        self.assertEqual("民事-一审-案件", sanitize_path_part(" 民事/一审:案件 "))
        self.assertEqual("uncategorized", sanitize_path_part(""))

    def test_single_output_builds_dry_run_plan_without_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "起诉状.txt"
            source.write_text("case filing", encoding="utf-8")
            output = tmp_path / "agent-output.json"
            write_output(output, source)

            plan = build_filing_plan(output, tmp_path / "filing")

            self.assertEqual("FILING_PLAN_CREATED", plan["agent_state"])
            self.assertEqual({"ready": 1}, plan["status_counts"])
            item = plan["items"][0]
            self.assertEqual("ready", item["status"])
            self.assertIn("民事-一审案件", item["target"])
            self.assertFalse(Path(item["target"]).exists())

    def test_manifest_blocks_review_failed_and_low_confidence_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            outputs = tmp_path / "outputs"
            outputs.mkdir()
            files = []
            for name, state, confidence in (
                ("ok.txt", "COMPLETED", "high"),
                ("review.txt", "NEEDS_REVIEW", "medium"),
                ("failed.txt", "FAILED", "high"),
                ("low.txt", "COMPLETED", "low"),
            ):
                source = tmp_path / name
                source.write_text(name, encoding="utf-8")
                output = outputs / f"{name}.json"
                write_output(output, source, state=state, confidence=confidence)
                files.append({
                    "file_id": name,
                    "file_path": str(source),
                    "agent_state": state,
                    "confidence": confidence,
                    "output": str(output),
                })
            manifest = tmp_path / "manifest.json"
            manifest.write_text(json.dumps({"run_id": "run-1", "files": files}, ensure_ascii=False), encoding="utf-8")

            plan = build_filing_plan(manifest, tmp_path / "filing")

            self.assertEqual(4, plan["item_count"])
            self.assertEqual(1, plan["status_counts"]["ready"])
            self.assertEqual(3, plan["status_counts"]["blocked"])
            reasons = " ".join(item["reason"] for item in plan["items"])
            self.assertIn("agent_state is NEEDS_REVIEW", reasons)
            self.assertIn("agent_state is FAILED", reasons)
            self.assertIn("confidence is low", reasons)

    def test_apply_copy_creates_target_file_and_writes_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "起诉状.txt"
            source.write_text("copy me", encoding="utf-8")
            output = tmp_path / "agent-output.json"
            write_output(output, source)

            plan = build_filing_plan(output, tmp_path / "filing", action="copy", apply=True)
            plan_path = write_filing_plan(plan, tmp_path / "plan.json")

            item = plan["items"][0]
            self.assertEqual("copied", item["status"])
            self.assertTrue(Path(item["target"]).exists())
            self.assertTrue(source.exists())
            self.assertTrue(plan_path.exists())

    def test_apply_move_moves_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "裁定书.txt"
            source.write_text("move me", encoding="utf-8")
            output = tmp_path / "agent-output.json"
            write_output(output, source)

            plan = build_filing_plan(output, tmp_path / "filing", action="move", apply=True)

            item = plan["items"][0]
            self.assertEqual("moved", item["status"])
            self.assertTrue(Path(item["target"]).exists())
            self.assertFalse(source.exists())


if __name__ == "__main__":
    unittest.main()
