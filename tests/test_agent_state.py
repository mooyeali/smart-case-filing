import json
import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.state import AgentState, AgentStep, AgentTraceStore


class AgentTraceStoreTest(unittest.TestCase):
    def test_appends_and_loads_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            store = AgentTraceStore(trace_path)
            step = AgentStep(
                run_id="run-1",
                file_path="sample.pdf",
                state=AgentState.EXTRACTED,
                tool="extract_content",
                input_summary={"path": "sample.pdf"},
                output_summary={"file_type": "pdf"},
            )

            store.append(step)
            loaded = store.load()

            self.assertEqual(1, len(loaded))
            self.assertEqual(AgentState.EXTRACTED, loaded[0].state)
            self.assertEqual("extract_content", loaded[0].tool)

    def test_trace_file_is_json_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            store = AgentTraceStore(trace_path)
            store.append(AgentStep(
                run_id="run-1",
                file_path="a.txt",
                state=AgentState.STARTED,
                tool="start",
                input_summary={},
                output_summary={},
            ))

            raw = trace_path.read_text(encoding="utf-8").strip()
            parsed = json.loads(raw)
            self.assertEqual("STARTED", parsed["state"])


if __name__ == "__main__":
    unittest.main()
