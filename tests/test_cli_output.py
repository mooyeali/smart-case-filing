import contextlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


sys.modules.setdefault("pandas", types.SimpleNamespace())

import file_directory_predictor as fdp
from file_directory_predictor import PredictionResult


class FakeCatalog:
    entries = []
    case_types = []
    categories = []


class FakeCatalogLoader:
    def __init__(self, xlsx_path):
        self.xlsx_path = Path(xlsx_path)

    def load(self):
        return FakeCatalog()


class FakeDirectoryPredictor:
    def __init__(self, catalog):
        self.catalog = catalog

    def predict(self, file_path):
        return PredictionResult(
            file_path=str(file_path),
            file_type="text",
            predicted_case_type="民事二审案件编目规则",
            predicted_volume="正卷",
            predicted_second_level_directory="上诉状及相关材料",
            predicted_material_category="上诉状",
            predicted_catalog_example="上诉状",
            confidence="high",
            reasoning="测试输出",
            vlm_analysis={"available": False, "reason": "测试"},
            llm_analysis={"available": False, "reason": "测试"},
        )


class CliOutputTest(unittest.TestCase):
    def run_main(self, argv, program_dir):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(sys, "argv", argv), \
                patch.object(fdp, "CatalogLoader", FakeCatalogLoader), \
                patch.object(fdp, "DirectoryPredictor", FakeDirectoryPredictor), \
                patch.object(fdp, "PROGRAM_DIR", Path(program_dir), create=True), \
                contextlib.redirect_stdout(stdout), \
                contextlib.redirect_stderr(stderr):
            fdp.main()
        return stdout.getvalue(), stderr.getvalue()

    def test_writes_output_and_log_to_explicit_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_file = tmp_path / "sample.txt"
            catalog_file = tmp_path / "catalog.xlsx"
            output_file = tmp_path / "result.json"
            log_file = tmp_path / "run.log"
            input_file.write_text("content", encoding="utf-8")
            catalog_file.write_text("catalog", encoding="utf-8")

            self.run_main([
                "file_directory_predictor.py",
                str(input_file),
                "--catalog", str(catalog_file),
                "--json",
                "--output", str(output_file),
                "--log", str(log_file),
            ], tmp_path)

            self.assertIn('"predicted_material_category": "上诉状"', output_file.read_text(encoding="utf-8"))
            self.assertIn("[加载编目规则]", log_file.read_text(encoding="utf-8"))

    def test_writes_output_and_log_to_program_dir_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_file = tmp_path / "sample.txt"
            catalog_file = tmp_path / "catalog.xlsx"
            input_file.write_text("content", encoding="utf-8")
            catalog_file.write_text("catalog", encoding="utf-8")

            self.run_main([
                "file_directory_predictor.py",
                str(input_file),
                "--catalog", str(catalog_file),
                "--json",
            ], tmp_path)

            output_file = tmp_path / "file_directory_predictor_output.txt"
            log_file = tmp_path / "file_directory_predictor.log"
            self.assertTrue(output_file.exists())
            self.assertTrue(log_file.exists())
            self.assertIn('"predicted_material_category": "上诉状"', output_file.read_text(encoding="utf-8"))
            self.assertIn("[加载编目规则]", log_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
