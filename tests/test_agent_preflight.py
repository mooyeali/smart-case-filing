import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_directory_predictor as fdp
from smart_case_filing.agent.preflight import check_model_preflight


class AgentPreflightTest(unittest.TestCase):
    def test_http_configuration_selects_http_mode(self):
        data = check_model_preflight({
            "AI_BASE_URL": "https://example.test/v1",
            "AI_API_KEY": "sk-test",
            "AI_MODEL": "model-test",
        })

        self.assertTrue(data["http"]["configured"])
        self.assertEqual("https://example.test/v1", data["http"]["base_url"])
        self.assertTrue(data["http"]["api_key_configured"])
        self.assertEqual("model-test", data["http"]["model"])
        self.assertEqual("http", data["selected_mode"])

    def test_unconfigured_mode_without_http_or_legacy(self):
        with patch("smart_case_filing.agent.preflight.shutil.which", return_value=None):
            data = check_model_preflight({})

        self.assertFalse(data["http"]["configured"])
        self.assertFalse(data["legacy_z_ai"]["available"])
        self.assertEqual("unconfigured", data["selected_mode"])

    def test_cli_preflight_runs_without_input_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_file = Path(tmp) / "preflight.json"
            log_file = Path(tmp) / "preflight.log"
            with patch.object(sys, "argv", [
                "file_directory_predictor.py",
                "--agent",
                "--agent-preflight",
                "--output", str(output_file),
                "--log", str(log_file),
            ]), patch("file_directory_predictor.check_model_preflight", return_value={
                "http": {"configured": False},
                "legacy_z_ai": {"available": False},
                "selected_mode": "unconfigured",
            }), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                fdp.main()

            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("unconfigured", data["selected_mode"])


if __name__ == "__main__":
    unittest.main()
