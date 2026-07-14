from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from smart_case_filing.agent.tools import ToolResult


@dataclass
class RetryPolicy:
    max_attempts: int = 1
    initial_delay_seconds: float = 0.0
    backoff_factor: float = 2.0
    retryable_errors: tuple[str, ...] = field(default_factory=lambda: (
        "timeout",
        "temporar",
        "rate limit",
        "connection",
        "unavailable",
        "server error",
    ))
    sleep: Callable[[float], None] = time.sleep

    def is_retryable(self, result: ToolResult) -> bool:
        if result.ok:
            return False
        error = (result.error or "").lower()
        return any(marker in error for marker in self.retryable_errors)

    def run(self, func: Callable[[], ToolResult]) -> ToolResult:
        attempts = 0
        delay = self.initial_delay_seconds
        last = ToolResult(ok=False, error="retry policy did not run")
        max_attempts = max(1, self.max_attempts)
        while attempts < max_attempts:
            attempts += 1
            last = func()
            if last.ok or attempts >= max_attempts or not self.is_retryable(last):
                data = dict(last.data or {})
                data["attempt_count"] = attempts
                return ToolResult(ok=last.ok, data=data, error=last.error)
            if delay > 0:
                self.sleep(delay)
            delay *= self.backoff_factor
        data = dict(last.data or {})
        data["attempt_count"] = attempts
        return ToolResult(ok=last.ok, data=data, error=last.error)


NO_RETRY = RetryPolicy(max_attempts=1)
