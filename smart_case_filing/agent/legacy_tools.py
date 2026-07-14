from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


def summarize_file_content(fc) -> dict:
    return {
        "file_path": str(fc.file_path),
        "file_type": fc.file_type,
        "text_length": len(fc.text or ""),
        "text_preview": fc.text_preview(300) if hasattr(fc, "text_preview") else (fc.text or "")[:300],
        "image_count": len(fc.image_paths or []),
        "page_count": fc.page_count,
        "extract_error": fc.extract_error,
    }


def summarize_candidates(candidates: list, limit: int = 5) -> list[dict]:
    summaries = []
    for e in candidates[:limit]:
        summaries.append({
            "case_type": e.case_type,
            "volume": e.volume,
            "second_level_directory": e.second_level_directory,
            "material_category": e.material_category,
            "catalog_name_example": e.catalog_name_example,
        })
    return summaries


def _build_fusion(payload: dict) -> dict:
    llm = payload.get("llm_analysis", {}) or {}
    vlm = payload.get("vlm_analysis", {}) or {}
    key_info = ""
    if vlm.get("available") and not vlm.get("parse_error"):
        key_info += "视觉特征: " + (vlm.get("visual_features", "") or "") + "\n"
        key_info += "OCR文本: " + (vlm.get("ocr_text", "") or "") + "\n"
    if llm.get("available") and not llm.get("parse_error"):
        key_info += "关键短语: " + (llm.get("key_phrases", "") or "") + "\n"
        key_info += "内容摘要: " + (llm.get("summary", "") or "") + "\n"

    return {
        "doc_type": payload.get("doc_type") or llm.get("doc_type_guess") or vlm.get("doc_type_guess", ""),
        "volume": payload.get("volume") or llm.get("volume_guess") or vlm.get("volume_guess", ""),
        "case_clues": payload.get("case_clues") or llm.get("case_clues") or vlm.get("case_clues", ""),
        "key_info": payload.get("key_info", key_info),
        "case_number": payload.get("case_number", ""),
        "file_name": payload.get("file_name", ""),
        "file_type": payload.get("file_type", ""),
        "text_preview": payload.get("text_preview", ""),
        "confidence": payload.get("confidence") or llm.get("confidence") or vlm.get("confidence", "low"),
    }


def build_legacy_tool_registry(catalog, model_client=None):
    import file_directory_predictor as legacy

    predictor = legacy.DirectoryPredictor(catalog, model_client=model_client)
    extractor = legacy.ContentExtractor()
    registry = AgentToolRegistry()

    def extract_content(payload: dict) -> ToolResult:
        fc = extractor.extract(Path(payload["file_path"]))
        data = summarize_file_content(fc)
        data["_fc"] = fc
        data["case_number"] = fc.file_path.parent.name
        data["file_name"] = fc.file_path.name
        return ToolResult(ok=True, data=data)

    def analyze_visual(payload: dict) -> ToolResult:
        fc = payload.get("_fc")
        if not fc:
            return ToolResult(ok=False, error="missing extracted file content")
        analysis = predictor.vlm.analyze(fc)
        return ToolResult(ok=True, data={"vlm_analysis": analysis})

    def analyze_text(payload: dict) -> ToolResult:
        fc = payload.get("_fc")
        if not fc:
            return ToolResult(ok=False, error="missing extracted file content")
        analysis = predictor.llm.analyze_text(fc)
        return ToolResult(ok=True, data={"llm_analysis": analysis})

    def retrieve_candidates(payload: dict) -> ToolResult:
        fusion = _build_fusion(payload)
        keywords = predictor._extract_keywords(fusion)
        candidates = catalog.search_candidates(
            keywords,
            case_number=fusion.get("case_number", ""),
        )
        used_fallback = False
        if not candidates:
            candidates = catalog.search_candidates([])
            used_fallback = True
        return ToolResult(ok=True, data={
            "keywords": keywords,
            "candidate_count": len(candidates),
            "candidate_summaries": summarize_candidates(candidates),
            "used_fallback": used_fallback,
            "_candidates": candidates,
        })

    def select_catalog(payload: dict) -> ToolResult:
        candidates = payload.get("_candidates") or []
        if not candidates:
            return ToolResult(ok=False, error="no catalog candidates")
        raw = predictor.model_client.chat(
            "select best catalog candidate",
            system=legacy.LLMAnalyzer.SYSTEM,
            thinking=True,
            timeout=legacy.CLI_TIMEOUT,
        )
        match = predictor._parse_match(raw, candidates)
        return ToolResult(ok=True, data={
            "match": match,
            "candidate_count": len(candidates),
            "candidate_summaries": summarize_candidates(candidates),
        })

    def finalize_prediction(payload: dict) -> ToolResult:
        fc = payload.get("_fc")
        match = payload.get("match", {}) or {}
        result = legacy.PredictionResult(
            file_path=str(fc.file_path) if fc else payload.get("file_path", ""),
            file_type=fc.file_type if fc else payload.get("file_type", ""),
            predicted_case_type=match.get("case_type", ""),
            predicted_volume=match.get("volume", ""),
            predicted_second_level_directory=match.get("second_level_directory", ""),
            predicted_material_category=match.get("material_category", ""),
            predicted_catalog_example=match.get("catalog_name_example", ""),
            confidence=match.get("confidence", "low"),
            reasoning=match.get("reasoning", ""),
            vlm_analysis=payload.get("vlm_analysis", {}),
            llm_analysis=payload.get("llm_analysis", {}),
            matched_entries=match.get("matched_entries", []),
        )
        data = result.to_dict()
        data["candidate_summaries"] = payload.get("candidate_summaries", [])
        return ToolResult(ok=True, data=data)

    registry.register("extract_content", extract_content)
    registry.register("analyze_visual", analyze_visual)
    registry.register("analyze_text", analyze_text)
    registry.register("retrieve_candidates", retrieve_candidates)
    registry.register("select_catalog", select_catalog)
    registry.register("finalize_prediction", finalize_prediction)
    return registry
