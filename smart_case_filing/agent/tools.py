from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ToolResult:
    ok: bool
    data: dict = field(default_factory=dict)
    error: str = ""


class AgentToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable[[dict], ToolResult]] = {}

    def register(self, name: str, func: Callable[[dict], ToolResult]) -> None:
        self._tools[name] = func

    def run(self, name: str, payload: dict) -> ToolResult:
        func = self._tools.get(name)
        if not func:
            return ToolResult(ok=False, error=f"unknown tool: {name}")
        try:
            return func(payload)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))
