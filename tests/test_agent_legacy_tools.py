import tempfile
import unittest
from pathlib import Path

from file_directory_predictor import CatalogEntry, CatalogIndex
from smart_case_filing.agent.legacy_tools import (
    build_legacy_tool_registry,
    summarize_candidates,
    summarize_file_content,
)


def entry(case_type, material_category):
    return CatalogEntry(
        case_type=case_type,
        volume="正卷",
        second_level_directory=f"{material_category}目录",
        constraint="必选",
        material_category=material_category,
        catalog_name_example=f"{material_category}示例",
    )


class SequenceModelClient:
    def __init__(self, chat_responses=None, vision_response=""):
        self.chat_responses = list(chat_responses or [])
        self.vision_response = vision_response

    def chat(self, prompt, system=None, thinking=False, timeout=180):
        if self.chat_responses:
            return self.chat_responses.pop(0)
        return ""

    def vision(self, prompt, image_paths, thinking=False, timeout=180):
        return self.vision_response


class LegacyAgentToolsTest(unittest.TestCase):
    def make_catalog(self):
        return CatalogIndex(entries=[
            entry("民事一审案件编目规则", "民事起诉状"),
            entry("刑事一审案件编目规则", "起诉书"),
        ]).build()

    def test_registry_runs_extraction_with_summary_and_internal_fc(self):
        registry = build_legacy_tool_registry(self.make_catalog(), model_client=SequenceModelClient())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.txt"
            path.write_text("民事起诉状\n这是很长的正文内容", encoding="utf-8")

            result = registry.run("extract_content", {"file_path": str(path)})

            self.assertTrue(result.ok, result.error)
            self.assertEqual("text", result.data["file_type"])
            self.assertGreater(result.data["text_length"], 0)
            self.assertIn("text_preview", result.data)
            self.assertIn("_fc", result.data)

    def test_summaries_do_not_include_full_internal_objects(self):
        registry = build_legacy_tool_registry(self.make_catalog(), model_client=SequenceModelClient())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.txt"
            path.write_text("民事起诉状", encoding="utf-8")
            extracted = registry.run("extract_content", {"file_path": str(path)}).data

            summary = summarize_file_content(extracted["_fc"])

            self.assertNotIn("_fc", summary)
            self.assertEqual("text", summary["file_type"])

    def test_analyze_text_uses_injected_model_client(self):
        model = SequenceModelClient([
            '{"doc_type_guess":"民事起诉状","volume_guess":"正卷","case_clues":"民事","confidence":"high"}'
        ])
        registry = build_legacy_tool_registry(self.make_catalog(), model_client=model)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.txt"
            path.write_text("民事起诉状", encoding="utf-8")
            extracted = registry.run("extract_content", {"file_path": str(path)}).data

            result = registry.run("analyze_text", extracted)

            self.assertTrue(result.ok, result.error)
            self.assertEqual("民事起诉状", result.data["llm_analysis"]["doc_type_guess"])

    def test_retrieve_candidates_returns_compact_summaries(self):
        registry = build_legacy_tool_registry(self.make_catalog(), model_client=SequenceModelClient())
        result = registry.run("retrieve_candidates", {
            "file_name": "起诉状.txt",
            "case_number": "(2026)京0105民初1号",
            "doc_type": "民事起诉状",
            "case_clues": "民事",
            "key_info": "",
        })

        self.assertTrue(result.ok, result.error)
        self.assertEqual(1, result.data["candidate_count"])
        self.assertEqual("民事起诉状", result.data["candidate_summaries"][0]["material_category"])
        self.assertIn("_candidates", result.data)

    def test_select_catalog_keeps_fields_from_selected_candidate(self):
        model = SequenceModelClient([
            '{"selected_index":"1","case_type":"模型编造","material_category":"模型编造","confidence":"high"}'
        ])
        registry = build_legacy_tool_registry(self.make_catalog(), model_client=model)
        candidates = self.make_catalog().entries[:1]

        result = registry.run("select_catalog", {
            "file_name": "sample.txt",
            "doc_type": "民事起诉状",
            "case_clues": "民事",
            "_candidates": candidates,
        })

        self.assertTrue(result.ok, result.error)
        match = result.data["match"]
        self.assertEqual("民事一审案件编目规则", match["case_type"])
        self.assertEqual("民事起诉状", match["material_category"])

    def test_summarize_candidates_limits_output(self):
        summaries = summarize_candidates(self.make_catalog().entries, limit=1)

        self.assertEqual(1, len(summaries))
        self.assertEqual("民事起诉状", summaries[0]["material_category"])


if __name__ == "__main__":
    unittest.main()
