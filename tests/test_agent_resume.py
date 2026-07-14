import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_directory_predictor as fdp
from smart_case_filing.agent.state import AgentState, AgentStep, AgentTraceStore


def append_step(trace_path, state, output_summary=None, error=""):
    AgentTraceStore(trace_path).append(AgentStep(
        run_id="run-1",
        file_path="sample.txt",
        state=state,
        tool=state.value.lower(),
        input_summary={},
        output_summary=output_summary or {},
        error=error,
    ))


class AgentResumeTest(unittest.TestCase):
    def run_resume(self, trace_path):
        output_file = trace_path.parent / "resume-output.json"
        log_file = trace_path.parent / "resume.log"
        with patch.object(sys, "argv", [
            "file_directory_predictor.py",
            "--agent",
            "--resume", str(trace_path),
            "--output", str(output_file),
            "--log", str(log_file),
        ]), patch.object(fdp, "build_legacy_tool_registry", side_effect=AssertionError("tools must not run")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            fdp.main()
        return json.loads(output_file.read_text(encoding="utf-8"))

    def test_resume_completed_trace_returns_summary_without_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            append_step(trace_path, AgentState.COMPLETED, {
                "predicted_material_category": "complaint",
                "confidence": "high",
            })

            data = self.run_resume(trace_path)

            self.assertEqual("COMPLETED", data["agent_state"])
            self.assertTrue(data["resume"])
            self.assertEqual("complaint", data["predicted_material_category"])

    def test_resume_failed_trace_returns_error_without_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            append_step(trace_path, AgentState.FAILED, error="model unavailable")

            data = self.run_resume(trace_path)

            self.assertEqual("FAILED", data["agent_state"])
            self.assertEqual("model unavailable", data["error"])

    def test_resume_missing_trace_returns_failed_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.run_resume(Path(tmp) / "missing.jsonl")

            self.assertEqual("FAILED", data["agent_state"])
            self.assertIn("trace does not exist", data["error"])

    def test_resume_partial_trace_is_explicitly_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            append_step(trace_path, AgentState.TEXT_ANALYZED)

            data = self.run_resume(trace_path)

            self.assertEqual("FAILED", data["agent_state"])
            self.assertEqual("TEXT_ANALYZED", data["last_state"])
            self.assertEqual("partial resume is not supported in phase two", data["reason"])

    def test_resume_needs_review_trace_returns_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            append_step(trace_path, AgentState.NEEDS_REVIEW, {"confidence": "low"})

            data = self.run_resume(trace_path)

            self.assertEqual("NEEDS_REVIEW", data["agent_state"])
            self.assertEqual("low", data["confidence"])


if __name__ == "__main__":
    unittest.main()
