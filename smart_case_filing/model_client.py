from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Protocol


def redact_secret(text: str) -> str:
    def repl(match):
        token = match.group(1)
        if len(token) <= 8:
            return "sk-****"
        return f"{token[:6]}...{token[-4:]}"

    return re.sub(r"(sk-[A-Za-z0-9._-]+)", repl, text or "")


class ModelClient(Protocol):
    def chat(self, prompt: str, system: Optional[str] = None,
             thinking: bool = False, timeout: int = 180) -> str:
        ...

    def vision(self, prompt: str, image_paths: list,
               thinking: bool = False, timeout: int = 180) -> str:
        ...


@dataclass
class LegacyFunctionModelClient:
    chat_func: callable
    vision_func: callable

    def chat(self, prompt: str, system: Optional[str] = None,
             thinking: bool = False, timeout: int = 180) -> str:
        return self.chat_func(prompt, system=system, thinking=thinking, timeout=timeout)

    def vision(self, prompt: str, image_paths: list,
               thinking: bool = False, timeout: int = 180) -> str:
        return self.vision_func(prompt, image_paths, thinking=thinking, timeout=timeout)


@dataclass
class FakeModelClient:
    responses: dict[str, str] = field(default_factory=dict)

    def chat(self, prompt: str, system: Optional[str] = None,
             thinking: bool = False, timeout: int = 180) -> str:
        return self.responses.get("chat", "")

    def vision(self, prompt: str, image_paths: list,
               thinking: bool = False, timeout: int = 180) -> str:
        return self.responses.get("vision", "")
