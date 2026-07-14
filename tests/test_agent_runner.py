import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.runner import AgentRunner
from smart_case_filing.agent.state import AgentState, AgentTraceStore
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


class AgentRunnerTest(unittest.TestCase):
    def make_registry(self):
        registry = AgentToolRegistry()
        registry.register(
            "extract_content",
            lambda payload: ToolResult(ok=True, data={
                "file_path": payload["file_path"],
                "file_type": "text",
                "text_length": 5,
                "text_preview": "民事起诉状",
                "image_count": 0,
            }),
        )
        registry.register(
            "analyze_visual",
            lambda payload: ToolResult(ok=True, data={"vlm_analysis": {"available": False}}),
        )
        registry.register(
            "analyze_text",
            lambda payload: ToolResult(ok=True, data={"llm_analysis": {"doc_type_guess": "民事起诉状", "confidence": "high"}}),
        )
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
                "confidence": "high",
            },
        }))
        registry.register("finalize_prediction", lambda payload: ToolResult(ok=True, data={
            "predicted_case_type": payload["match"]["case_type"],
            "predicted_volume": payload["match"]["volume"],
            "predicted_second_level_directory": payload["match"]["second_level_directory"],
            "predicted_material_category": payload["match"]["material_category"],
            "confidence": payload["match"]["confidence"],
        }))
        return registry

    def test_runner_completes_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(self.make_registry(), trace)

            result = runner.run("run-1", "sample.txt")

            self.assertEqual(AgentState.COMPLETED, result["state"])
            self.assertEqual("民事起诉状", result["prediction"]["predicted_material_category"])
            self.assertEqual(7, len(trace.load()))

    def test_runner_stops_on_failed_tool(self):
        registry = AgentToolRegistry()
        registry.register("extract_content", lambda payload: ToolResult(ok=False, error="read failed"))
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(registry, trace)

            result = runner.run("run-1", "missing.pdf")

            self.assertEqual(AgentState.FAILED, result["state"])
            self.assertIn("read failed", result["error"])


if __name__ == "__main__":
    unittest.main()
