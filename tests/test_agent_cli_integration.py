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


def make_registry(confidence="high"):
    registry = AgentToolRegistry()
    registry.register("extract_content", lambda payload: ToolResult(ok=True, data={
        "file_path": payload["file_path"],
        "file_type": "text",
        "text_length": 5,
        "text_preview": "民事起诉状",
        "image_count": 0,
    }))
    registry.register("analyze_visual", lambda payload: ToolResult(ok=True, data={
        "vlm_analysis": {"available": False, "reason": "no visual input"}
    }))
    registry.register("analyze_text", lambda payload: ToolResult(ok=True, data={
        "llm_analysis": {"doc_type_guess": "民事起诉状", "confidence": "high"}
    }))
    registry.register("retrieve_candidates", lambda payload: ToolResult(ok=True, data={
        "candidate_count": 1,
        "candidate_summaries": [{"material_category": "民事起诉状"}],
    }))
    registry.register("select_catalog", lambda payload: ToolResult(ok=True, data={
        "match": {
            "case_type": "民事一审案件编目规则",
            "volume": "正卷",
            "second_level_directory": "起诉状及相关材料",
            "material_category": "民事起诉状",
            "catalog_name_example": "民事起诉状",
            "confidence": confidence,
            "reasoning": "测试",
        },
        "candidate_summaries": [{"material_category": "民事起诉状"}],
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


class AgentCliIntegrationTest(unittest.TestCase):
    def run_agent(self, tmp_path, confidence="high"):
        input_file = tmp_path / "sample.txt"
        catalog_file = tmp_path / "catalog.xlsx"
        trace_file = tmp_path / "trace.jsonl"
        output_file = tmp_path / "out.json"
        log_file = tmp_path / "run.log"
        review_file = tmp_path / "review.json"
        input_file.write_text("民事起诉状", encoding="utf-8")
        catalog_file.write_text("fake", encoding="utf-8")

        with patch.object(sys, "argv", [
            "file_directory_predictor.py",
            str(input_file),
            "--catalog", str(catalog_file),
            "--agent",
            "--trace", str(trace_file),
            "--review-output", str(review_file),
            "--json",
            "--output", str(output_file),
            "--log", str(log_file),
        ]), patch.object(fdp, "CatalogLoader", FakeCatalogLoader), \
                patch.object(fdp, "build_legacy_tool_registry", lambda catalog: make_registry(confidence)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            fdp.main()
        return output_file, trace_file, review_file

    def test_agent_mode_outputs_legacy_fields_and_agent_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_file, trace_file, review_file = self.run_agent(Path(tmp), confidence="high")

            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("COMPLETED", data["agent_state"])
            self.assertEqual("民事起诉状", data["predicted_material_category"])
            self.assertTrue(trace_file.exists())
            self.assertFalse(review_file.exists())

    def test_agent_mode_writes_review_for_low_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_file, trace_file, review_file = self.run_agent(Path(tmp), confidence="low")

            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("NEEDS_REVIEW", data["agent_state"])
            self.assertTrue(trace_file.exists())
            self.assertTrue(review_file.exists())
            review = json.loads(review_file.read_text(encoding="utf-8"))
            self.assertEqual("NEEDS_REVIEW", review["agent_state"])


if __name__ == "__main__":
    unittest.main()
