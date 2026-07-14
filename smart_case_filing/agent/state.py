from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class AgentState(str, Enum):
    STARTED = "STARTED"
    EXTRACTED = "EXTRACTED"
    VISUAL_ANALYZED = "VISUAL_ANALYZED"
    TEXT_ANALYZED = "TEXT_ANALYZED"
    CANDIDATES_RETRIEVED = "CANDIDATES_RETRIEVED"
    MATCHED = "MATCHED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class AgentStep:
    run_id: str
    file_path: str
    state: AgentState
    tool: str
    input_summary: dict = field(default_factory=dict)
    output_summary: dict = field(default_factory=dict)
    error: str = ""
    created_at: float = field(default_factory=time.time)

    def to_jsonable(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_jsonable(cls, data: dict) -> "AgentStep":
        return cls(
            run_id=data["run_id"],
            file_path=data["file_path"],
            state=AgentState(data["state"]),
            tool=data["tool"],
            input_summary=data.get("input_summary", {}),
            output_summary=data.get("output_summary", {}),
            error=data.get("error", ""),
            created_at=float(data.get("created_at", time.time())),
        )


class AgentTraceStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, step: AgentStep) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(step.to_jsonable(), ensure_ascii=False) + "\n")

    def load(self) -> list[AgentStep]:
        if not self.path.exists():
            return []
        steps = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                steps.append(AgentStep.from_jsonable(json.loads(line)))
        return steps
