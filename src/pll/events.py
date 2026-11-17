"""Versioned experiment event logging (JSONL)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVENT_SCHEMA_VERSION = "1.0"
DEFAULT_LOG_DIR = Path(__file__).resolve().parents[2] / "outputs" / "events"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def event_path(session_id: str, log_dir: Path | None = None) -> Path:
    root = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root / f"session_{session_id}.jsonl"


def append_event(
    session_id: str,
    event_type: str,
    *,
    learner_id: str,
    payload: dict[str, Any] | None = None,
    log_dir: Path | None = None,
) -> Path:
    """Append one JSONL event. Returns the log path."""
    path = event_path(session_id, log_dir=log_dir)
    record = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "ts": _now(),
        "session_id": session_id,
        "learner_id": learner_id,
        "event_type": event_type,
        **(payload or {}),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def log_item_response(
    session_id: str,
    *,
    learner_id: str,
    item_id: str,
    skill: str,
    method: str | None,
    response: Any,
    correct: bool,
    outcome_type: str,
    context: list[float] | None = None,
    policy_probs: list[float] | None = None,
    latency_ms: float | None = None,
    content_version: str | int | None = None,
    model_id: str | None = None,
    respondent: str = "human",
    extra: dict[str, Any] | None = None,
    log_dir: Path | None = None,
) -> Path:
    payload = {
        "item_id": item_id,
        "skill": skill,
        "method": method,
        "response": response,
        "correct": bool(correct),
        "outcome_type": outcome_type,  # practice | immediate_post | delayed_24h | diagnostic
        "context": context,
        "policy_probs": policy_probs,
        "latency_ms": latency_ms,
        "content_version": content_version,
        "model_id": model_id,
        "respondent": respondent,
    }
    if extra:
        payload.update(extra)
    return append_event(
        session_id,
        "item_response",
        learner_id=learner_id,
        payload=payload,
        log_dir=log_dir,
    )


def read_events(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_all_events(log_dir: Path | None = None) -> list[dict[str, Any]]:
    root = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("session_*.jsonl")):
        rows.extend(read_events(path))
    return rows
