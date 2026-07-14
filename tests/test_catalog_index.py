import sys
import types
import unittest


sys.modules.setdefault("pandas", types.SimpleNamespace())

import file_directory_predictor
from file_directory_predictor import CatalogEntry, CatalogIndex, DirectoryPredictor


def entry(case_type, material_category):
    return CatalogEntry(
        case_type=case_type,
        volume="正卷",
        second_level_directory=f"{material_category}目录",
        constraint="必选",
        material_category=material_category,
        catalog_name_example=material_category,
    )


class CatalogIndexSearchCandidatesTest(unittest.TestCase):
    def test_case_number_loads_all_rules_for_matching_case_type(self):
        catalog = CatalogIndex(entries=[
            entry("民事一审案件编目规则", "民事起诉状"),
            entry("民事一审案件编目规则", "证据材料"),
            entry("刑事一审案件编目规则", "起诉书"),
        ]).build()

        candidates = catalog.search_candidates(
            keywords=["起诉"],
            case_number="(2026)京0105民初123号",
            top_n=1,
        )

        self.assertEqual(
            ["民事起诉状", "证据材料"],
            [candidate.material_category for candidate in candidates],
        )

    def test_predictor_passes_parent_directory_as_case_number(self):
        catalog = CatalogIndex(entries=[
            entry("民事二审案件编目规则", "上诉状"),
            entry("刑事二审案件编目规则", "抗诉书"),
        ]).build()
        predictor = DirectoryPredictor(catalog)
        fusion = {
            "file_name": "上诉状.pdf",
            "case_number": "(2026)京01民终456号",
            "doc_type": "上诉状",
            "case_clues": "民事 二审",
            "key_info": "",
        }

        captured = {}

        def fake_parse(raw, candidates):
            captured["candidates"] = candidates
            return {"confidence": "low", "matched_entries": []}

        original_chat = file_directory_predictor._run_zai_chat
        try:
            file_directory_predictor._run_zai_chat = (
                lambda *args, **kwargs: '{"selected_index": "1"}'
            )
            predictor._parse_match = fake_parse
            predictor._match_catalog(fusion)
        finally:
            file_directory_predictor._run_zai_chat = original_chat

        self.assertEqual(
            ["上诉状"],
            [candidate.material_category for candidate in captured["candidates"]],
        )


if __name__ == "__main__":
    unittest.main()
