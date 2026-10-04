from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from local_agent.foundation.process import atomic_write_text
from local_agent.runtime.task_contract import task_timeout_for

MAX_DEDUPE_KEY_CHARS = 200
RECENT_COMPLETION_TTL_SECONDS = 30 * 60
ADMISSION_GRACE_SECONDS = 10 * 60
_DEDUPE_KEY_RE = re.compile(r"^[A-Za-z0-9._:/-]+$")

PendingTask = tuple[Path, dict[str, Any]]


@dataclass(frozen=True)
class SuppressedTask:
    item: PendingTask
    duplicate_of: str
    queue_key: str
    execution_fingerprint: str
    reason: str


@dataclass(frozen=True)
class InvalidTask:
    item: PendingTask
    error: str


@dataclass(frozen=True)
class QueuePlan:
    candidates: tuple[PendingTask, ...]
    suppressed: tuple[SuppressedTask, ...]
    invalid: tuple[InvalidTask, ...]


def _serialized(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _structured_commands(task: dict[str, Any], field: str) -> list[str]:
    commands: list[str] = []
    for item in task.get(field, []):
        if isinstance(item, dict):
            command = item.get("command")
            if isinstance(command, str):
                commands.append(command)
    return commands


def execution_contract(task: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic task effects while ignoring cosmetic execution metadata."""
    return {
        "agent_binding": task.get("agent_binding"),
        "mode": task.get("mode", "commands"),
        "work_branch": task.get("work_branch", "main"),
        "allow_write": task.get("allow_write", False),
        "resources": task.get("resources", []),
        "patch": task.get("patch"),
        "writes": task.get("writes", []),
        "deletes": task.get("deletes", []),
        "commands": task.get("commands", []),
        "verify_commands": task.get("verify_commands", []),
        "steps": _structured_commands(task, "steps"),
        "verify_steps": _structured_commands(task, "verify_steps"),
    }


def execution_fingerprint(task: dict[str, Any]) -> str:
    """Fingerprint task effects independently of id, stage names and timeout/log tuning."""
    return hashlib.sha256(_serialized(execution_contract(task))).hexdigest()


def explicit_dedupe_key(task: dict[str, Any]) -> str | None:
    raw = task.get("dedupe_key")
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("dedupe_key must be a string")
    if not raw or raw != raw.strip() or len(raw) > MAX_DEDUPE_KEY_CHARS:
        raise ValueError(
            f"dedupe_key must be canonical non-empty text up to {MAX_DEDUPE_KEY_CHARS} characters"
        )
    if _DEDUPE_KEY_RE.fullmatch(raw) is None:
        raise ValueError("dedupe_key contains unsupported characters")
    return raw


def queue_key(task: dict[str, Any]) -> str:
    """Return branch-scoped intent identity or fall back to the exact effect fingerprint."""
    explicit = explicit_dedupe_key(task)
    if explicit is not None:
        branch = str(task.get("work_branch", "main"))
        return f"intent:{branch}:{explicit}"
    return f"effect:{execution_fingerprint(task)}"


def _receipt_path(state_dir: Path, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return state_dir / "task-dedupe" / f"{digest}.json"


def _claim_path(state_dir: Path, task_id: str) -> Path:
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    return state_dir / "claims" / f"{digest}.json"


def _read_receipt(
    state_dir: Path,
    key: str,
    *,
    now_epoch: float,
) -> dict[str, Any] | None:
    path = _receipt_path(state_dir, key)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError):
        path.unlink(missing_ok=True)
        return None

    if not isinstance(payload, dict) or payload.get("version") != 1:
        path.unlink(missing_ok=True)
        return None
    expires_at = payload.get("expires_at_epoch")
    if not isinstance(expires_at, (int, float)) or isinstance(expires_at, bool):
        path.unlink(missing_ok=True)
        return None
    if float(expires_at) <= now_epoch:
        path.unlink(missing_ok=True)
        return None
    task_id = payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        path.unlink(missing_ok=True)
        return None

    state = payload.get("state")
    if state == "admitted":
        if not _claim_path(state_dir, task_id).exists():
            path.unlink(missing_ok=True)
            return None
    elif state != "completed":
        path.unlink(missing_ok=True)
        return None
    return payload


def plan_pending(
    state_dir: Path,
    pending: list[PendingTask],
    *,
    now_epoch: float | None = None,
) -> QueuePlan:
    """Keep one task per queue identity and suppress recent cross-chat repeats."""
    now_value = time.time() if now_epoch is None else now_epoch
    seen: dict[str, str] = {}
    candidates: list[PendingTask] = []
    suppressed: list[SuppressedTask] = []
    invalid: list[InvalidTask] = []

    for item in pending:
        _, task = item
        task_id = str(task.get("id", ""))
        try:
            key = queue_key(task)
        except ValueError as exc:
            invalid.append(InvalidTask(item=item, error=str(exc)))
            continue
        fingerprint = execution_fingerprint(task)

        receipt = _read_receipt(state_dir, key, now_epoch=now_value)
        if receipt is not None and receipt["task_id"] != task_id:
            suppressed.append(
                SuppressedTask(
                    item=item,
                    duplicate_of=str(receipt["task_id"]),
                    queue_key=key,
                    execution_fingerprint=fingerprint,
                    reason="recent_duplicate",
                )
            )
            continue

        prior = seen.get(key)
        if prior is not None and prior != task_id:
            suppressed.append(
                SuppressedTask(
                    item=item,
                    duplicate_of=prior,
                    queue_key=key,
                    execution_fingerprint=fingerprint,
                    reason="queued_duplicate",
                )
            )
            continue

        seen[key] = task_id
        candidates.append(item)

    return QueuePlan(tuple(candidates), tuple(suppressed), tuple(invalid))


def _write_receipt(
    state_dir: Path,
    task: dict[str, Any],
    *,
    state: str,
    outcome: str | None,
    expires_at_epoch: float,
    now_epoch: float,
) -> None:
    key = queue_key(task)
    payload = {
        "version": 1,
        "queue_key": key,
        "task_id": str(task["id"]),
        "execution_fingerprint": execution_fingerprint(task),
        "state": state,
        "outcome": outcome,
        "updated_at_epoch": now_epoch,
        "expires_at_epoch": expires_at_epoch,
    }
    path = _receipt_path(state_dir, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


def record_admission(
    state_dir: Path,
    task: dict[str, Any],
    *,
    now_epoch: float | None = None,
) -> None:
    """Hold a queue identity while the task has a durable claim."""
    now_value = time.time() if now_epoch is None else now_epoch
    _write_receipt(
        state_dir,
        task,
        state="admitted",
        outcome=None,
        expires_at_epoch=now_value + task_timeout_for(task) + ADMISSION_GRACE_SECONDS,
        now_epoch=now_value,
    )


def record_completion(
    state_dir: Path,
    task: dict[str, Any],
    outcome: str,
    *,
    now_epoch: float | None = None,
) -> None:
    """Keep a short receipt so late duplicates from another chat are drained, not rerun."""
    now_value = time.time() if now_epoch is None else now_epoch
    _write_receipt(
        state_dir,
        task,
        state="completed",
        outcome=outcome,
        expires_at_epoch=now_value + RECENT_COMPLETION_TTL_SECONDS,
        now_epoch=now_value,
    )
