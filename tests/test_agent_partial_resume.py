import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_directory_predictor as fdp
from smart_case_filing.agent.runner import AgentRunner
from smart_case_filing.agent.state import AgentState, AgentStep, AgentTraceStore
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


def append_step(trace_path, state, output_summary=None):
    AgentTraceStore(trace_path).append(AgentStep(
        run_id="run-1",
        file_path="sample.txt",
        state=state,
        tool=state.value.lower(),
        input_summary={},
        output_summary=output_summary or {},
    ))


def make_registry(calls=None):
    calls = calls if calls is not None else []
    registry = AgentToolRegistry()
    registry.register("extract_content", lambda payload: calls.append("extract_content") or ToolResult(ok=True, data={
        "file_path": payload["file_path"],
        "file_type": "text",
        "text_length": 5,
        "image_count": 0,
    }))
    registry.register("analyze_visual", lambda payload: calls.append("analyze_visual") or ToolResult(ok=True, data={
        "vlm_analysis": {"available": False}
    }))
    registry.register("analyze_text", lambda payload: calls.append("analyze_text") or ToolResult(ok=True, data={
        "llm_analysis": {"available": True, "confidence": "high"}
    }))
    registry.register("retrieve_candidates", lambda payload: calls.append("retrieve_candidates") or ToolResult(ok=True, data={
        "candidate_count": 1,
        "candidate_summaries": [{"material_category": "complaint"}],
    }))
    registry.register("select_catalog", lambda payload: calls.append("select_catalog") or ToolResult(ok=True, data={
        "match": {
            "case_type": "civil",
            "volume": "main",
            "second_level_directory": "complaints",
            "material_category": "complaint",
            "catalog_name_example": "complaint",
            "confidence": "high",
            "reasoning": "resumed",
        },
        "candidate_summaries": [{"material_category": "complaint"}],
    }))
    registry.register("finalize_prediction", lambda payload: calls.append("finalize_prediction") or ToolResult(ok=True, data={
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


class AgentPartialResumeTest(unittest.TestCase):
    def test_runner_resumes_from_text_analyzed_without_rerunning_prior_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            append_step(trace_path, AgentState.STARTED, {"file_path": "sample.txt"})
            append_step(trace_path, AgentState.EXTRACTED, {
                "file_path": "sample.txt",
                "file_type": "text",
                "text_length": 5,
                "image_count": 0,
            })
            append_step(trace_path, AgentState.VISUAL_ANALYZED, {
                "vlm_analysis": {"available": False}
            })
            append_step(trace_path, AgentState.TEXT_ANALYZED, {
                "llm_analysis": {"available": True}
            })
            calls = []
            runner = AgentRunner(make_registry(calls), AgentTraceStore(trace_path))

            result = runner.resume("run-1", "sample.txt", AgentTraceStore(trace_path).load())

            self.assertEqual(AgentState.COMPLETED, result["state"])
            self.assertEqual(["retrieve_candidates", "select_catalog", "finalize_prediction"], calls)

    def test_runner_fails_clearly_when_resume_context_is_insufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            append_step(trace_path, AgentState.EXTRACTED, {
                "file_path": "sample.txt",
                "file_type": "text",
                "text_length": 5,
                "image_count": 0,
            })
            runner = AgentRunner(make_registry(), AgentTraceStore(trace_path))

            result = runner.resume("run-1", "sample.txt", AgentTraceStore(trace_path).load())

            self.assertEqual(AgentState.FAILED, result["state"])
            self.assertIn("extracted file content is not available", result["error"])

    def test_cli_partial_resume_continues_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace_path = tmp_path / "trace.jsonl"
            catalog_file = tmp_path / "catalog.xlsx"
            output_file = tmp_path / "out.json"
            log_file = tmp_path / "run.log"
            catalog_file.write_text("fake", encoding="utf-8")
            append_step(trace_path, AgentState.STARTED, {"file_path": "sample.txt"})
            append_step(trace_path, AgentState.TEXT_ANALYZED, {
                "file_path": "sample.txt",
                "file_type": "text",
                "text_length": 5,
                "image_count": 0,
                "llm_analysis": {"available": True},
                "vlm_analysis": {"available": False},
            })

            with patch.object(sys, "argv", [
                "file_directory_predictor.py",
                "--agent",
                "--resume", str(trace_path),
                "--catalog", str(catalog_file),
                "--output", str(output_file),
                "--log", str(log_file),
            ]), patch.object(fdp, "CatalogLoader", FakeCatalogLoader), \
                    patch.object(fdp, "build_legacy_tool_registry", lambda catalog: make_registry()), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                fdp.main()

            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("COMPLETED", data["agent_state"])
            self.assertTrue(data["resume"])
            self.assertEqual("TEXT_ANALYZED", data["last_state"])

    def test_batch_resume_skips_terminal_files_and_resumes_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir = tmp_path / "run"
            traces_dir = run_dir / "traces"
            traces_dir.mkdir(parents=True)
            catalog_file = tmp_path / "catalog.xlsx"
            catalog_file.write_text("fake", encoding="utf-8")
            partial_trace = traces_dir / "partial.trace.jsonl"
            append_step(partial_trace, AgentState.TEXT_ANALYZED, {
                "file_path": "partial.txt",
                "file_type": "text",
                "text_length": 5,
                "image_count": 0,
                "llm_analysis": {"available": True},
            })
            manifest = {
                "run_id": "run-1",
                "files": [
                    {
                        "file_path": "done.txt",
                        "agent_state": "COMPLETED",
                        "trace": str(traces_dir / "done.trace.jsonl"),
                    },
                    {
                        "file_path": "partial.txt",
                        "agent_state": "TEXT_ANALYZED",
                        "trace": str(partial_trace),
                    },
                ],
            }
            (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            output_file = tmp_path / "out.json"
            log_file = tmp_path / "run.log"

            with patch.object(sys, "argv", [
                "file_directory_predictor.py",
                "--agent",
                "--resume", str(run_dir),
                "--catalog", str(catalog_file),
                "--output", str(output_file),
                "--log", str(log_file),
            ]), patch.object(fdp, "CatalogLoader", FakeCatalogLoader), \
                    patch.object(fdp, "build_legacy_tool_registry", lambda catalog: make_registry()), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                fdp.main()

            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("BATCH_RESUMED", data["agent_state"])
            self.assertEqual(1, data["resumed_count"])
            self.assertEqual(1, data["skipped_count"])
            self.assertEqual("COMPLETED", data["resumed"][0]["agent_state"])
            updated_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            partial = [item for item in updated_manifest["files"] if item["file_path"] == "partial.txt"][0]
            self.assertEqual("COMPLETED", partial["agent_state"])
            self.assertTrue(Path(partial["output"]).exists())
            self.assertTrue(Path(data["review_index"]).exists())


if __name__ == "__main__":
    unittest.main()
