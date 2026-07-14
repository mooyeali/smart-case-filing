import tempfile
import unittest
import contextlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import file_directory_predictor as fdp
from smart_case_filing.agent.retry import RetryPolicy
from smart_case_filing.agent.runner import AgentRunner
from smart_case_filing.agent.state import AgentState, AgentTraceStore
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


class AgentRetryPolicyTest(unittest.TestCase):
    def make_success_registry(self):
        registry = AgentToolRegistry()
        registry.register("extract_content", lambda payload: ToolResult(ok=True, data={
            "file_path": payload["file_path"],
            "file_type": "text",
            "text_length": 0,
            "image_count": 0,
        }))
        registry.register("retrieve_candidates", lambda payload: ToolResult(ok=True, data={
            "candidate_count": 1,
            "candidate_summaries": [],
        }))
        registry.register("select_catalog", lambda payload: ToolResult(ok=True, data={
            "match": {
                "case_type": "civil",
                "volume": "main",
                "second_level_directory": "complaints",
                "material_category": "complaint",
                "catalog_name_example": "complaint",
                "confidence": "high",
                "reasoning": "ok",
            }
        }))
        registry.register("finalize_prediction", lambda payload: ToolResult(ok=True, data={
            "file_path": payload["file_path"],
            "file_type": "text",
            "predicted_case_type": "civil",
            "predicted_volume": "main",
            "predicted_second_level_directory": "complaints",
            "predicted_material_category": "complaint",
            "predicted_catalog_example": "complaint",
            "confidence": "high",
            "reasoning": "ok",
            "vlm_analysis": payload.get("vlm_analysis", {}),
            "llm_analysis": payload.get("llm_analysis", {}),
            "matched_entries": [],
        }))
        return registry

    def test_retries_transient_tool_failure(self):
        calls = {"extract": 0}
        registry = self.make_success_registry()

        def flaky_extract(payload):
            calls["extract"] += 1
            if calls["extract"] == 1:
                return ToolResult(ok=False, error="temporary model unavailable")
            return ToolResult(ok=True, data={
                "file_path": payload["file_path"],
                "file_type": "text",
                "text_length": 0,
                "image_count": 0,
            })

        registry.register("extract_content", flaky_extract)

        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(
                registry,
                trace,
                retry_policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0),
            )

            result = runner.run("run-1", "sample.txt")

            self.assertEqual(AgentState.COMPLETED, result["state"])
            self.assertEqual(2, calls["extract"])
            extracted = [step for step in trace.load() if step.state == AgentState.EXTRACTED][0]
            self.assertEqual(2, extracted.output_summary["attempt_count"])

    def test_does_not_retry_deterministic_failure(self):
        calls = {"retrieve": 0}
        registry = self.make_success_registry()

        def no_candidates(payload):
            calls["retrieve"] += 1
            return ToolResult(ok=False, error="no catalog candidates")

        registry.register("retrieve_candidates", no_candidates)

        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(
                registry,
                trace,
                retry_policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0),
            )

            result = runner.run("run-1", "sample.txt")

            self.assertEqual(AgentState.FAILED, result["state"])
            self.assertEqual(1, calls["retrieve"])
            failed = [step for step in trace.load() if step.state == AgentState.CANDIDATES_RETRIEVED][0]
            self.assertEqual(1, failed.output_summary.get("attempt_count", 1))

    def test_cli_retry_options_are_used_by_agent_runner(self):
        class FakeCatalog:
            entries = []
            case_types = []
            categories = []

        class FakeCatalogLoader:
            def __init__(self, path):
                self.path = path

            def load(self):
                return FakeCatalog()

        calls = {"extract": 0}
        registry = self.make_success_registry()

        def flaky_extract(payload):
            calls["extract"] += 1
            if calls["extract"] == 1:
                return ToolResult(ok=False, error="custom transient")
            return ToolResult(ok=True, data={
                "file_path": payload["file_path"],
                "file_type": "text",
                "text_length": 0,
                "image_count": 0,
            })

        registry.register("extract_content", flaky_extract)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_file = tmp_path / "sample.txt"
            catalog_file = tmp_path / "catalog.xlsx"
            output_file = tmp_path / "out.json"
            log_file = tmp_path / "run.log"
            trace_file = tmp_path / "trace.jsonl"
            input_file.write_text("content", encoding="utf-8")
            catalog_file.write_text("fake", encoding="utf-8")

            with patch.object(sys, "argv", [
                "file_directory_predictor.py",
                str(input_file),
                "--catalog", str(catalog_file),
                "--agent",
                "--trace", str(trace_file),
                "--agent-retry-attempts", "2",
                "--agent-retry-errors", "custom transient",
                "--output", str(output_file),
                "--log", str(log_file),
            ]), patch.object(fdp, "CatalogLoader", FakeCatalogLoader), \
                    patch.object(fdp, "build_legacy_tool_registry", lambda catalog: registry), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                fdp.main()

            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("COMPLETED", data["agent_state"])
            self.assertEqual(2, calls["extract"])


if __name__ == "__main__":
    unittest.main()
