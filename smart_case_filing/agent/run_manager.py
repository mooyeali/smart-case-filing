from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from smart_case_filing.agent.state import AgentState
from smart_case_filing.agent.review import (
    ReviewPackageWriter,
    build_review_decision_payload,
    build_review_index_payload,
)


TERMINAL_STATES = {
    AgentState.COMPLETED.value,
    AgentState.NEEDS_REVIEW.value,
    AgentState.FAILED.value,
}


def make_run_id() -> str:
    return "agent-" + uuid.uuid4().hex[:12]


def make_file_id(file_path: str) -> str:
    path = str(Path(file_path))
    stem = Path(file_path).stem or "file"
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]
    safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in stem).strip("-")
    return f"{safe_stem or 'file'}-{digest}"


def state_value(state) -> str:
    return state.value if hasattr(state, "value") else str(state)


class AgentRunManager:
    def __init__(self, root: Path, run_id: str | None = None, reviews_dir: Path | None = None):
        self.root = Path(root)
        self.run_id = run_id or make_run_id()
        self.run_dir = self.root / self.run_id if self.root.name != self.run_id else self.root
        self.traces_dir = self.run_dir / "traces"
        self.reviews_dir = Path(reviews_dir) if reviews_dir else self.run_dir / "reviews"
        self.decisions_dir = self.run_dir / "decisions"
        self.outputs_dir = self.run_dir / "outputs"
        self.manifest_path = self.run_dir / "manifest.json"

    def ensure(self) -> None:
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self.reviews_dir.mkdir(parents=True, exist_ok=True)
        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            now = time.time()
            self.write_manifest({
                "run_id": self.run_id,
                "created_at": now,
                "updated_at": now,
                "status_counts": {
                    AgentState.COMPLETED.value: 0,
                    AgentState.NEEDS_REVIEW.value: 0,
                    AgentState.FAILED.value: 0,
                },
                "files": [],
            })

    def paths_for(self, file_path: str) -> dict:
        file_id = make_file_id(file_path)
        return {
            "file_id": file_id,
            "trace": self.traces_dir / f"{file_id}.trace.jsonl",
            "review": self.reviews_dir / f"{file_id}.review.json",
            "output": self.outputs_dir / f"{file_id}.json",
        }

    def load_manifest(self) -> dict:
        self.ensure()
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def write_manifest(self, manifest: dict) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def record_file(self, file_path: str, agent_result: dict, paths: dict | None = None) -> dict:
        self.ensure()
        paths = paths or self.paths_for(file_path)
        state = state_value(agent_result.get("agent_state") or agent_result.get("state") or AgentState.FAILED)
        prediction = agent_result.get("prediction") or agent_result
        entry = {
            "file_id": paths["file_id"],
            "file_path": str(file_path),
            "agent_state": state,
            "confidence": prediction.get("confidence", ""),
            "reasoning": prediction.get("reasoning", ""),
            "trace": str(paths["trace"]),
            "review": str(paths["review"]) if state in {AgentState.NEEDS_REVIEW.value, AgentState.FAILED.value} else "",
            "output": str(paths["output"]),
            "error": agent_result.get("error", ""),
        }

        manifest = self.load_manifest()
        files = [
            item for item in manifest.get("files", [])
            if item.get("file_id") != paths["file_id"] and item.get("file_path") != str(file_path)
        ]
        files.append(entry)
        manifest["files"] = files
        manifest["updated_at"] = time.time()
        manifest["status_counts"] = self._status_counts(files)
        self.write_manifest(manifest)
        return entry

    def summary(self) -> dict:
        manifest = self.load_manifest()
        return {
            "run_id": manifest["run_id"],
            "manifest": str(self.manifest_path),
            "run_dir": str(self.run_dir),
            "status_counts": manifest.get("status_counts", {}),
            "file_count": len(manifest.get("files", [])),
            "files": manifest.get("files", []),
        }

    def write_review_index(self) -> Path:
        manifest = self.load_manifest()
        index_path = self.reviews_dir / "index.json"
        ReviewPackageWriter(index_path).write(build_review_index_payload(manifest))
        return index_path

    def record_decision(self, decision: dict) -> dict:
        self.ensure()
        payload = build_review_decision_payload(decision)
        file_id = payload.get("file_id") or make_file_id(payload.get("file_path", "reviewed"))
        payload["file_id"] = file_id
        decision_path = self.decisions_dir / f"{file_id}.decision.json"
        ReviewPackageWriter(decision_path).write(payload)

        manifest = self.load_manifest()
        files = manifest.get("files", [])
        matched = False
        for item in files:
            if item.get("file_id") == file_id or (
                payload.get("file_path") and item.get("file_path") == payload.get("file_path")
            ):
                item["decision"] = payload.get("decision", "")
                item["decision_path"] = str(decision_path)
                item["reviewed_at"] = payload.get("created_at")
                matched = True
        if not matched:
            files.append({
                "file_id": file_id,
                "file_path": payload.get("file_path", ""),
                "agent_state": "",
                "confidence": "",
                "trace": "",
                "review": "",
                "output": "",
                "error": "",
                "decision": payload.get("decision", ""),
                "decision_path": str(decision_path),
                "reviewed_at": payload.get("created_at"),
            })
        manifest["files"] = files
        manifest["updated_at"] = time.time()
        self.write_manifest(manifest)
        return {
            "decision": payload.get("decision", ""),
            "decision_path": str(decision_path),
            "file_id": file_id,
            "manifest": str(self.manifest_path),
        }

    @staticmethod
    def _status_counts(files: list[dict]) -> dict:
        counts = {
            AgentState.COMPLETED.value: 0,
            AgentState.NEEDS_REVIEW.value: 0,
            AgentState.FAILED.value: 0,
        }
        for item in files:
            state = item.get("agent_state", "")
            if state in counts:
                counts[state] += 1
        return counts
