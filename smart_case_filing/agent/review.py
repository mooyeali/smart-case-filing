from __future__ import annotations

import json
from pathlib import Path

from smart_case_filing.model_client import redact_secret


class ReviewPackageWriter:
    def __init__(self, path: Path):
        self.path = Path(path)

    def write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, ensure_ascii=False, indent=2)
        self.path.write_text(redact_secret(raw) + "\n", encoding="utf-8")
