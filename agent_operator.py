#!/usr/bin/env python3
"""Persistent local operator state for emergency Local Agent controls."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_process import atomic_write_text, fsync_directory

STATE_DIR = Path.home() / "Library" / "Application Support" / "local-agent"
DISABLED_PATH = STATE_DIR / "disabled.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def disabled_state() -> dict[str, Any]:
    try:
        payload = json.loads(DISABLED_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def is_disabled() -> bool:
    return DISABLED_PATH.is_file()


def disable_agent(
    *,
    control_id: str | None = None,
    repository_id: str | None = None,
    reason: str = "operator_request",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": 1,
        "disabled": True,
        "disabled_at": now_iso(),
        "reason": reason,
    }
    if control_id:
        payload["control_id"] = control_id
    if repository_id:
        payload["repository_id"] = repository_id
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        DISABLED_PATH,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    )
    return payload


def enable_agent() -> bool:
    try:
        DISABLED_PATH.unlink()
    except FileNotFoundError:
        return False
    fsync_directory(DISABLED_PATH.parent)
    return True
