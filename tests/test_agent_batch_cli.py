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


def make_registry():
    registry = AgentToolRegistry()

    def confidence(payload):
        name = Path(payload["file_path"]).name
        return "low" if "review" in name else "high"

    registry.register("extract_content", lambda payload: ToolResult(ok=True, data={
        "file_path": payload["file_path"],
        "file_type": "text",
        "text_length": 10,
        "text_preview": "content",
        "image_count": 0,
    }))
    registry.register("analyze_visual", lambda payload: ToolResult(ok=True, data={
        "vlm_analysis": {"available": False}
    }))
    registry.register("analyze_text", lambda payload: ToolResult(ok=True, data={
        "llm_analysis": {"available": True, "confidence": "high"}
    }))
    registry.register("retrieve_candidates", lambda payload: ToolResult(ok=True, data={
        "candidate_count": 1,
        "candidate_summaries": [{"material_category": "complaint"}],
    }))
    registry.register("select_catalog", lambda payload: ToolResult(ok=True, data={
        "match": {
            "case_type": "civil",
            "volume": "main",
            "second_level_directory": "complaints",
            "material_category": "complaint",
            "catalog_name_example": "complaint",
            "confidence": confidence(payload),
            "reasoning": "batch test",
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


class AgentBatchCliTest(unittest.TestCase):
    def test_agent_batch_creates_manifest_and_per_file_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir()
            (input_dir / "complete.txt").write_text("complete", encoding="utf-8")
            (input_dir / "review.txt").write_text("review", encoding="utf-8")
            (input_dir / "nested").mkdir()
            (input_dir / "nested" / "ignored.txt").write_text("ignored", encoding="utf-8")
            catalog_file = tmp_path / "catalog.xlsx"
            catalog_file.write_text("fake", encoding="utf-8")
            run_dir = tmp_path / "agent-run"
            output_file = tmp_path / "batch-output.json"
            log_file = tmp_path / "batch.log"

            with patch.object(sys, "argv", [
                "file_directory_predictor.py",
                "--batch", str(input_dir),
                "--catalog", str(catalog_file),
                "--agent",
                "--trace", str(run_dir),
                "--json",
                "--output", str(output_file),
                "--log", str(log_file),
            ]), patch.object(fdp, "CatalogLoader", FakeCatalogLoader), \
                    patch.object(fdp, "build_legacy_tool_registry", lambda catalog: make_registry()), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                fdp.main()

            summary = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("BATCH_COMPLETED", summary["agent_state"])
            self.assertEqual(2, summary["file_count"])
            self.assertEqual({
                "COMPLETED": 1,
                "NEEDS_REVIEW": 1,
                "FAILED": 0,
            }, summary["status_counts"])

            manifest_path = Path(summary["manifest"])
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(2, len(manifest["files"]))
            for item in manifest["files"]:
                self.assertTrue(Path(item["trace"]).exists())
                self.assertTrue(Path(item["output"]).exists())
            review_items = [item for item in manifest["files"] if item["agent_state"] == "NEEDS_REVIEW"]
            self.assertEqual(1, len(review_items))
            self.assertTrue(Path(review_items[0]["review"]).exists())


if __name__ == "__main__":
    unittest.main()
