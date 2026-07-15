from __future__ import annotations

import json
from pathlib import Path


REVIEWABLE_STATES = {"NEEDS_REVIEW", "FAILED"}


def _manifest_path(path: Path) -> Path:
    path = Path(path)
    return path / "manifest.json" if path.is_dir() else path


def _issue(message: str, file_id: str = "", file_path: str = "") -> dict:
    return {
        "message": message,
        "file_id": file_id,
        "file_path": file_path,
    }


def _status_counts(files: list[dict]) -> dict:
    counts = {"COMPLETED": 0, "NEEDS_REVIEW": 0, "FAILED": 0}
    for item in files:
        state = item.get("agent_state", "")
        if state in counts:
            counts[state] += 1
    return counts


def audit_run(manifest_or_run_dir) -> dict:
    manifest_path = _manifest_path(Path(manifest_or_run_dir))
    issues = []
    if not manifest_path.exists():
        return {
            "valid": False,
            "manifest": str(manifest_path),
            "run_id": "",
            "status_counts": {},
            "file_count": 0,
            "review_count": 0,
            "decision_count": 0,
            "issues": [_issue(f"manifest does not exist: {manifest_path}")],
            "files": [],
        }

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "valid": False,
            "manifest": str(manifest_path),
            "run_id": "",
            "status_counts": {},
            "file_count": 0,
            "review_count": 0,
            "decision_count": 0,
            "issues": [_issue(f"manifest is not valid JSON: {exc}")],
            "files": [],
        }

    files = manifest.get("files", [])
    if not isinstance(files, list):
        issues.append(_issue("manifest files must be a list"))
        files = []

    actual_counts = _status_counts(files)
    if manifest.get("status_counts") and manifest.get("status_counts") != actual_counts:
        issues.append(_issue("manifest status_counts do not match file entries"))

    file_summaries = []
    reviewable_ids = set()
    for item in files:
        file_id = item.get("file_id", "")
        file_path = item.get("file_path", "")
        state = item.get("agent_state", "")
        if state in REVIEWABLE_STATES:
            reviewable_ids.add(file_id)
        for field in ("trace", "output"):
            value = item.get(field, "")
            if not value:
                issues.append(_issue(f"missing {field} path", file_id, file_path))
            elif not Path(value).exists():
                issues.append(_issue(f"{field} path does not exist: {value}", file_id, file_path))
        if state in REVIEWABLE_STATES:
            review = item.get("review", "")
            if not review:
                issues.append(_issue("missing review path", file_id, file_path))
            elif not Path(review).exists():
                issues.append(_issue(f"review path does not exist: {review}", file_id, file_path))
        decision_path = item.get("decision_path", "")
        if decision_path and not Path(decision_path).exists():
            issues.append(_issue(f"decision path does not exist: {decision_path}", file_id, file_path))
        file_summaries.append({
            "file_id": file_id,
            "file_path": file_path,
            "agent_state": state,
            "confidence": item.get("confidence", ""),
            "trace": item.get("trace", ""),
            "review": item.get("review", ""),
            "output": item.get("output", ""),
            "decision": item.get("decision", ""),
            "decision_path": decision_path,
            "error": item.get("error", ""),
        })

    review_index_path = _review_index_path(files, manifest_path)
    indexed_ids = set()
    if reviewable_ids:
        if not review_index_path:
            issues.append(_issue("review index path cannot be inferred"))
        elif not review_index_path.exists():
            issues.append(_issue(f"review index does not exist: {review_index_path}"))
        else:
            try:
                index = json.loads(review_index_path.read_text(encoding="utf-8"))
                indexed_ids = {item.get("file_id", "") for item in index.get("items", [])}
            except Exception as exc:
                issues.append(_issue(f"review index is not valid JSON: {exc}"))
    missing_index_ids = sorted(reviewable_ids - indexed_ids)
    for file_id in missing_index_ids:
        issues.append(_issue("review index does not include reviewable file", file_id=file_id))

    decision_count = sum(1 for item in files if item.get("decision_path"))
    return {
        "valid": not issues,
        "manifest": str(manifest_path),
        "run_id": manifest.get("run_id", ""),
        "status_counts": actual_counts,
        "file_count": len(files),
        "review_count": len(reviewable_ids),
        "decision_count": decision_count,
        "review_index": str(review_index_path) if review_index_path else "",
        "issues": issues,
        "files": file_summaries,
    }


def _review_index_path(files: list[dict], manifest_path: Path) -> Path | None:
    for item in files:
        review = item.get("review", "")
        if review:
            return Path(review).parent / "index.json"
    default = manifest_path.parent / "reviews" / "index.json"
    return default if default.exists() else None
