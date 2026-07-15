from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from smart_case_filing.agent.state import AgentState


REQUIRED_DIRECTORY_FIELDS = (
    "predicted_case_type",
    "predicted_volume",
    "predicted_second_level_directory",
    "predicted_material_category",
)


def sanitize_path_part(value: object, fallback: str = "uncategorized") -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\\/:*?\"<>|]+", "-", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:120] or fallback


def load_filing_records(source_path: Path) -> list[dict]:
    source_path = Path(source_path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("files"), list):
        records = []
        for item in payload.get("files", []):
            output = {}
            output_path = item.get("output", "")
            if output_path and Path(output_path).exists():
                output = json.loads(Path(output_path).read_text(encoding="utf-8"))
            record = dict(output)
            record.update({
                "file_id": item.get("file_id", record.get("file_id", "")),
                "file_path": item.get("file_path", record.get("file_path", "")),
                "agent_state": item.get("agent_state", record.get("agent_state", "")),
                "state": item.get("agent_state", record.get("state", "")),
                "confidence": item.get("confidence", record.get("confidence", "")),
                "manifest_output": output_path,
            })
            records.append(record)
        return records
    if isinstance(payload, dict):
        return [payload]
    raise ValueError("filing plan source must be an agent output JSON object or run manifest")


def build_filing_item(record: dict, filing_root: Path, action: str = "copy") -> dict:
    source = Path(record.get("file_path", ""))
    state = str(record.get("agent_state") or record.get("state") or "")
    confidence = str(record.get("confidence") or "").lower()
    reasons = []

    if state != AgentState.COMPLETED.value:
        reasons.append(f"agent_state is {state or 'missing'}")
    if confidence == "low":
        reasons.append("confidence is low")
    if not source.exists():
        reasons.append(f"source file does not exist: {source}")

    missing_fields = [field for field in REQUIRED_DIRECTORY_FIELDS if not str(record.get(field, "")).strip()]
    if missing_fields:
        reasons.append("missing directory fields: " + ", ".join(missing_fields))

    target = ""
    if not missing_fields and source.name:
        parts = [sanitize_path_part(record.get(field)) for field in REQUIRED_DIRECTORY_FIELDS]
        target = str(Path(filing_root).joinpath(*parts, sanitize_path_part(source.name, "file")))
        if Path(target).exists():
            reasons.append(f"target already exists: {target}")

    return {
        "file_id": record.get("file_id", ""),
        "source": str(source),
        "target": target,
        "action": action,
        "status": "blocked" if reasons else "ready",
        "reason": "; ".join(reasons),
        "agent_state": state,
        "confidence": record.get("confidence", ""),
        "predicted_case_type": record.get("predicted_case_type", ""),
        "predicted_volume": record.get("predicted_volume", ""),
        "predicted_second_level_directory": record.get("predicted_second_level_directory", ""),
        "predicted_material_category": record.get("predicted_material_category", ""),
    }


def execute_filing_item(item: dict) -> dict:
    if item.get("status") != "ready":
        return item
    source = Path(item["source"])
    target = Path(item["target"])
    if target.exists():
        item["status"] = "blocked"
        item["reason"] = f"target already exists: {target}"
        return item
    target.parent.mkdir(parents=True, exist_ok=True)
    if item.get("action") == "move":
        shutil.move(str(source), str(target))
        item["status"] = "moved"
    else:
        shutil.copy2(source, target)
        item["status"] = "copied"
    return item


def build_filing_plan(
    source_path: Path,
    filing_root: Path,
    action: str = "copy",
    apply: bool = False,
) -> dict:
    if action not in {"copy", "move"}:
        raise ValueError("action must be copy or move")

    records = load_filing_records(Path(source_path))
    items = [build_filing_item(record, Path(filing_root), action=action) for record in records]
    if apply:
        items = [execute_filing_item(item) for item in items]

    counts = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    return {
        "agent_state": "FILING_PLAN_APPLIED" if apply else "FILING_PLAN_CREATED",
        "state": "FILING_PLAN_APPLIED" if apply else "FILING_PLAN_CREATED",
        "source": str(Path(source_path)),
        "filing_root": str(Path(filing_root)),
        "action": action,
        "apply": bool(apply),
        "created_at": time.time(),
        "item_count": len(items),
        "status_counts": counts,
        "items": items,
    }


def write_filing_plan(plan: dict, output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path
