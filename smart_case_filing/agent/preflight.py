from __future__ import annotations

import os
import shutil


def check_model_preflight(env: dict | None = None) -> dict:
    env = env if env is not None else os.environ
    base_url = (env.get("AI_BASE_URL") or "").strip()
    api_key = (env.get("AI_API_KEY") or "").strip()
    model = (env.get("AI_MODEL") or "").strip()
    http_configured = bool(base_url and api_key and model)
    legacy_path = shutil.which("z-ai")
    legacy_available = bool(legacy_path)

    if http_configured:
        selected = "http"
    elif legacy_available:
        selected = "legacy-z-ai"
    else:
        selected = "unconfigured"

    return {
        "http": {
            "configured": http_configured,
            "base_url": base_url,
            "api_key_configured": bool(api_key),
            "model": model,
        },
        "legacy_z_ai": {
            "available": legacy_available,
            "path": legacy_path or "",
        },
        "selected_mode": selected,
    }
