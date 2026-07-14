from __future__ import annotations

import json
import time
from pathlib import Path

from smart_case_filing.model_client import redact_secret


def build_review_payload(agent_result: dict, trace_path: str) -> dict:
    prediction = agent_result.get("prediction") or {}
    source = prediction if prediction else agent_result
    state = agent_result.get("agent_state") or agent_result.get("state") or "FAILED"
    if hasattr(state, "value"):
        state = state.value

    return {
        "file_path": source.get("file_path") or agent_result.get("file_path", ""),
        "agent_state": str(state),
        "confidence": source.get("confidence", ""),
        "reasoning": source.get("reasoning", ""),
        "trace": str(trace_path),
        "candidate_summaries": (
            source.get("candidate_summaries")
            or agent_result.get("candidate_summaries")
            or agent_result.get("candidates")
            or []
        ),
        "llm_analysis": source.get("llm_analysis") or {},
        "vlm_analysis": source.get("vlm_analysis") or {},
        "error": agent_result.get("error", ""),
        "created_at": time.time(),
    }


def build_review_index_payload(manifest: dict) -> dict:
    items = []
    for item in manifest.get("files", []):
        if item.get("agent_state") not in {"NEEDS_REVIEW", "FAILED"}:
            continue
        items.append({
            "file_id": item.get("file_id", ""),
            "file_path": item.get("file_path", ""),
            "agent_state": item.get("agent_state", ""),
            "confidence": item.get("confidence", ""),
            "reasoning": item.get("reasoning", ""),
            "trace": item.get("trace", ""),
            "review": item.get("review", ""),
            "error": item.get("error", ""),
        })
    return {
        "run_id": manifest.get("run_id", ""),
        "created_at": time.time(),
        "review_count": len(items),
        "items": items,
    }


def build_review_decision_payload(decision: dict) -> dict:
    final_prediction = decision.get("final_prediction") or {}
    return {
        "file_id": decision.get("file_id", ""),
        "file_path": decision.get("file_path", ""),
        "decision": decision.get("decision", ""),
        "final_prediction": final_prediction,
        "reviewer": decision.get("reviewer", ""),
        "notes": decision.get("notes", ""),
        "created_at": time.time(),
    }


class ReviewPackageWriter:
    def __init__(self, path: Path):
        self.path = Path(path)

    def write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, ensure_ascii=False, indent=2)
        self.path.write_text(redact_secret(raw) + "\n", encoding="utf-8")
