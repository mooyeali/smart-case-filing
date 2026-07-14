import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.runner import AgentRunner
from smart_case_filing.agent.state import AgentState, AgentTraceStore
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


class AgentRunnerV2Test(unittest.TestCase):
    def make_registry(self, confidence="high"):
        registry = AgentToolRegistry()
        registry.register("extract_content", lambda payload: ToolResult(ok=True, data={
            "file_path": payload["file_path"],
            "file_type": "text",
            "text_length": 2000,
            "text_preview": "民事起诉状",
            "image_count": 0,
            "_fc": object(),
        }))
        registry.register("analyze_visual", lambda payload: ToolResult(ok=True, data={
            "vlm_analysis": {"available": False, "reason": "无可分析图像"}
        }))
        registry.register("analyze_text", lambda payload: ToolResult(ok=True, data={
            "llm_analysis": {"doc_type_guess": "民事起诉状", "confidence": "high"}
        }))
        registry.register("retrieve_candidates", lambda payload: ToolResult(ok=True, data={
            "candidate_count": 1,
            "candidate_summaries": [{"material_category": "民事起诉状"}],
            "_candidates": [object()],
        }))
        registry.register("select_catalog", lambda payload: ToolResult(ok=True, data={
            "match": {
                "case_type": "民事一审案件编目规则",
                "volume": "正卷",
                "second_level_directory": "起诉状及相关材料",
                "material_category": "民事起诉状",
                "confidence": confidence,
                "reasoning": "匹配",
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
            "predicted_catalog_example": "",
            "confidence": payload["match"]["confidence"],
            "reasoning": payload["match"]["reasoning"],
            "vlm_analysis": payload.get("vlm_analysis", {}),
            "llm_analysis": payload.get("llm_analysis", {}),
            "matched_entries": [],
            "candidate_summaries": payload.get("candidate_summaries", []),
        }))
        return registry

    def test_runner_records_full_filing_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(self.make_registry(), trace)

            result = runner.run("run-1", "sample.txt")
            states = [step.state for step in trace.load()]

            self.assertEqual(AgentState.COMPLETED, result["state"])
            self.assertEqual("民事起诉状", result["prediction"]["predicted_material_category"])
            self.assertEqual([
                AgentState.STARTED,
                AgentState.EXTRACTED,
                AgentState.VISUAL_ANALYZED,
                AgentState.TEXT_ANALYZED,
                AgentState.CANDIDATES_RETRIEVED,
                AgentState.MATCHED,
                AgentState.COMPLETED,
            ], states)

    def test_low_confidence_returns_needs_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(self.make_registry(confidence="low"), trace)

            result = runner.run("run-1", "sample.txt")

            self.assertEqual(AgentState.NEEDS_REVIEW, result["state"])
            self.assertEqual("low", result["prediction"]["confidence"])

    def test_failed_tool_records_failed_state(self):
        registry = AgentToolRegistry()
        registry.register("extract_content", lambda payload: ToolResult(ok=False, error="Authorization: Bearer sk-1234567890abcdef"))
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(registry, trace)

            result = runner.run("run-1", "missing.pdf")

            self.assertEqual(AgentState.FAILED, result["state"])
            self.assertNotIn("sk-1234567890abcdef", trace.load()[-1].error)

    def test_trace_summaries_drop_internal_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(self.make_registry(), trace)

            runner.run("run-1", "sample.txt")

            for step in trace.load():
                self.assertFalse(any(key.startswith("_") for key in step.input_summary))
                self.assertFalse(any(key.startswith("_") for key in step.output_summary))


if __name__ == "__main__":
    unittest.main()
