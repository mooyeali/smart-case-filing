import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_directory_predictor as fdp


class CliAgentModeTest(unittest.TestCase):
    def test_agent_mode_accepts_trace_and_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_file = tmp_path / "sample.txt"
            catalog_file = tmp_path / "catalog.xlsx"
            trace_file = tmp_path / "trace.jsonl"
            input_file.write_text("民事起诉状", encoding="utf-8")
            catalog_file.write_text("fake", encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.object(sys, "argv", [
                "file_directory_predictor.py",
                str(input_file),
                "--catalog", str(catalog_file),
                "--agent",
                "--trace", str(trace_file),
                "--json",
                "--output", str(tmp_path / "out.json"),
                "--log", str(tmp_path / "run.log"),
            ]), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with patch.object(fdp, "_run_agent_cli", lambda args: print("{\"state\": \"COMPLETED\"}")):
                    fdp.main()

            self.assertIn("COMPLETED", (tmp_path / "out.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
