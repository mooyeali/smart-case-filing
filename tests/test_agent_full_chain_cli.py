import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_directory_predictor as fdp
from smart_case_filing.agent.full_chain import run_fake_full_chain


class AgentFullChainCliTest(unittest.TestCase):
    def test_fake_full_chain_runner_generates_valid_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_fake_full_chain(Path(tmp) / "full-chain")

            self.assertEqual("FULL_CHAIN_TEST_COMPLETED", result["agent_state"])
            self.assertTrue(Path(result["manifest"]).exists())
            self.assertTrue(Path(result["review_index"]).exists())
            self.assertTrue(Path(result["decision_path"]).exists())
            self.assertTrue(Path(result["audit_report_md"]).exists())
            self.assertTrue(Path(result["audit_report_json"]).exists())
            self.assertTrue(result["audit"]["valid"])
            self.assertEqual({
                "COMPLETED": 1,
                "NEEDS_REVIEW": 1,
                "FAILED": 1,
            }, result["audit"]["status_counts"])

    def test_cli_full_chain_test_runs_without_input_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_file = Path(tmp) / "summary.json"
            log_file = Path(tmp) / "run.log"
            run_output = Path(tmp) / "generated"
            with patch.object(sys, "argv", [
                "file_directory_predictor.py",
                "--agent",
                "--agent-full-chain-test", str(run_output),
                "--output", str(output_file),
                "--log", str(log_file),
            ]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                fdp.main()

            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("FULL_CHAIN_TEST_COMPLETED", data["agent_state"])
            self.assertTrue(data["audit"]["valid"])
            self.assertTrue(Path(data["manifest"]).exists())


if __name__ == "__main__":
    unittest.main()
