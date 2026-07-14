import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_directory_predictor as fdp
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


class FakeCatalog:
    entries = []
    case_types = []
    categories = []


class FakeCatalogLoader:
    def __init__(self, path):
        self.path = path

    def load(self):
        return FakeCatalog()


def make_full_chain_registry():
    registry = AgentToolRegistry()

    def name(payload):
        return Path(payload["file_path"]).name

    def confidence(payload):
        return "low" if "review" in name(payload) else "high"

    registry.register("extract_content", lambda payload: ToolResult(ok=True, data={
        "file_path": payload["file_path"],
        "file_type": "text",
        "text_length": 20,
        "text_preview": "fake legal filing",
        "image_count": 0,
    }))
    registry.register("analyze_visual", lambda payload: ToolResult(ok=True, data={
        "vlm_analysis": {"available": False, "skipped": True}
    }))
    registry.register("analyze_text", lambda payload: ToolResult(ok=True, data={
        "llm_analysis": {"available": True, "doc_type_guess": "complaint", "confidence": "high"}
    }))

    def retrieve_candidates(payload):
        if "failed" in name(payload):
            return ToolResult(ok=False, error="no catalog candidates")
        return ToolResult(ok=True, data={
            "candidate_count": 1,
            "candidate_summaries": [{"material_category": "complaint"}],
        })

    registry.register("retrieve_candidates", retrieve_candidates)
    registry.register("select_catalog", lambda payload: ToolResult(ok=True, data={
        "match": {
            "case_type": "civil",
            "volume": "main",
            "second_level_directory": "complaints",
            "material_category": "complaint",
            "catalog_name_example": "complaint",
            "confidence": confidence(payload),
            "reasoning": "fake full-chain selection",
        },
        "candidate_summaries": [{"material_category": "complaint"}],
    }))
    registry.register("finalize_prediction", lambda payload: ToolResult(ok=True, data={
        "file_path": payload["file_path"],
        "file_type": "text",
        "predicted_case_type": payload["match"]["case_type"],
        "predicted_volume": payload["match"]["volume"],
        "predicted_second_level_directory": payload["match"]["second_level_directory"],
        "predicted_material_category": payload["match"]["material_category"],
        "predicted_catalog_example": payload["match"]["catalog_name_example"],
        "confidence": payload["match"]["confidence"],
        "reasoning": payload["match"]["reasoning"],
        "vlm_analysis": payload.get("vlm_analysis", {}),
        "llm_analysis": payload.get("llm_analysis", {}),
        "matched_entries": [],
        "candidate_summaries": payload.get("candidate_summaries", []),
    }))
    return registry


class AgentFullChainTest(unittest.TestCase):
    def run_main(self, argv):
        with patch.object(sys, "argv", argv), \
                patch.object(fdp, "CatalogLoader", FakeCatalogLoader), \
                patch.object(fdp, "build_legacy_tool_registry", lambda catalog: make_full_chain_registry()), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            fdp.main()

    def test_fake_batch_full_chain_and_resume_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir()
            for name in ("completed.txt", "review.txt", "failed.txt"):
                (input_dir / name).write_text(name, encoding="utf-8")
            catalog_file = tmp_path / "catalog.xlsx"
            catalog_file.write_text("fake", encoding="utf-8")
            run_dir = tmp_path / "agent-run"
            output_file = tmp_path / "batch.json"
            log_file = tmp_path / "batch.log"

            self.run_main([
                "file_directory_predictor.py",
                "--batch", str(input_dir),
                "--catalog", str(catalog_file),
                "--agent",
                "--trace", str(run_dir),
                "--json",
                "--output", str(output_file),
                "--log", str(log_file),
            ])

            summary = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("BATCH_COMPLETED", summary["agent_state"])
            self.assertEqual({
                "COMPLETED": 1,
                "NEEDS_REVIEW": 1,
                "FAILED": 1,
            }, summary["status_counts"])
            manifest = json.loads(Path(summary["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(3, len(manifest["files"]))
            for item in manifest["files"]:
                self.assertTrue(Path(item["trace"]).exists())
                self.assertTrue(Path(item["output"]).exists())
            review_index = json.loads(Path(summary["review_index"]).read_text(encoding="utf-8"))
            self.assertEqual(2, review_index["review_count"])

            resume_output = tmp_path / "resume.json"
            self.run_main([
                "file_directory_predictor.py",
                "--agent",
                "--resume", summary["manifest"],
                "--catalog", str(catalog_file),
                "--output", str(resume_output),
                "--log", str(tmp_path / "resume.log"),
            ])

            resume = json.loads(resume_output.read_text(encoding="utf-8"))
            self.assertEqual("BATCH_RESUMED", resume["agent_state"])
            self.assertEqual(0, resume["resumed_count"])
            self.assertEqual(3, resume["skipped_count"])

            review_item = [item for item in manifest["files"] if item["agent_state"] == "NEEDS_REVIEW"][0]
            decision_file = tmp_path / "decision.json"
            decision_file.write_text(json.dumps({
                "file_id": review_item["file_id"],
                "file_path": review_item["file_path"],
                "decision": "approved",
                "reviewer": "reviewer-a",
                "notes": "looks correct",
            }), encoding="utf-8")
            decision_output = tmp_path / "decision-output.json"
            self.run_main([
                "file_directory_predictor.py",
                "--agent",
                "--resume", summary["manifest"],
                "--review-decision", str(decision_file),
                "--output", str(decision_output),
                "--log", str(tmp_path / "decision.log"),
            ])

            decision = json.loads(decision_output.read_text(encoding="utf-8"))
            self.assertEqual("REVIEW_DECISION_RECORDED", decision["agent_state"])
            updated_manifest = json.loads(Path(summary["manifest"]).read_text(encoding="utf-8"))
            updated_item = [item for item in updated_manifest["files"] if item.get("file_id") == review_item["file_id"]][0]
            self.assertEqual("approved", updated_item["decision"])
            self.assertTrue(Path(updated_item["decision_path"]).exists())


if __name__ == "__main__":
    unittest.main()
