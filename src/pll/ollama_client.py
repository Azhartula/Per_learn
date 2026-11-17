"""Local Ollama client for on-laptop (GPU) lesson generation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("PLL_OLLAMA_MODEL", "qwen2.5:7b")


class OllamaError(RuntimeError):
    pass


def is_reachable(host: str = DEFAULT_HOST, timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(host.rstrip("/") + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def list_models(host: str = DEFAULT_HOST) -> list[str]:
    req = urllib.request.Request(host.rstrip("/") + "/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m.get("name", "") for m in data.get("models", [])]


def ensure_model(model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST) -> str:
    names = list_models(host)
    if any(model == n or n.startswith(model + ":") or model.startswith(n.split(":")[0]) for n in names):
        # Prefer exact tag match when present.
        for n in names:
            if n == model or n.startswith(model):
                return n
    raise OllamaError(
        f"Model {model!r} not found in Ollama ({names or 'no models'}). "
        f"Run: ollama pull {model}"
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def chat_json(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    temperature: float = 0.2,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Call Ollama /api/chat and parse a JSON object from the reply."""
    model = ensure_model(model, host)
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_predict": 1200,
        },
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Year 5 maths tutor. Reply with a single JSON object only. "
                    "Use the provided correct answers exactly — do not invent different answers."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        host.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise OllamaError(f"Ollama request failed: {exc}") from exc

    content = data.get("message", {}).get("content", "")
    if not content:
        raise OllamaError(f"Empty Ollama response: {data!r}")
    try:
        return json.loads(_strip_fences(content))
    except json.JSONDecodeError as exc:
        raise OllamaError(f"Ollama did not return valid JSON: {content[:400]!r}") from exc
