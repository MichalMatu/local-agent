"""Durable, bounded notification events for remotely published task results."""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_agent.foundation.process import atomic_write_text, fsync_directory

EVENT_SCHEMA_VERSION = 1
EVENT_TYPE_TASK_RESULT_READY = "task_result_ready"
MAX_OUTBOX_EVENTS = 256
EVENT_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_EVENT_BYTES = 4096
DEFAULT_STATE_DIR = Path.home() / "Library" / "Application Support" / "local-agent"
OUTBOX_RELATIVE = Path("bridge-events") / "outbox"
CONTROL_BINDING_RELATIVE = Path(".agent") / "binding.json"

_REPOSITORY_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
_EVENT_ID_RE = re.compile(r"^evt-[0-9a-f]{32}$")
_STATUS_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_DIGEST_RE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
_EVENT_IDENTITY_FIELDS = (
    "schema_version",
    "event_id",
    "event_type",
    "repository_id",
    "repository",
    "agent_binding",
    "task_id",
    "task_digest",
    "result_status",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def outbox_dir(state_dir: Path | None = None) -> Path:
    return (state_dir or DEFAULT_STATE_DIR) / OUTBOX_RELATIVE


def _canonical_binding(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("agent_binding must be a canonical UUID string")
    try:
        canonical = str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError("agent_binding must be a canonical UUID string") from exc
    if value != canonical:
        raise ValueError("agent_binding must use canonical lowercase UUID form")
    return canonical


def _load_control_identity(control_dir: Path) -> tuple[str, str, str]:
    path = control_dir / CONTROL_BINDING_RELATIVE
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError(f"invalid repository control binding: {path}")
    repository_id = payload.get("repository_id")
    repository = payload.get("repository")
    if not isinstance(repository_id, str) or not _REPOSITORY_ID_RE.fullmatch(repository_id):
        raise ValueError("invalid repository_id in control binding")
    if not isinstance(repository, str) or not _REPOSITORY_RE.fullmatch(repository):
        raise ValueError("invalid repository in control binding")
    return repository_id, repository, _canonical_binding(payload.get("agent_binding"))


def _event_id(
    repository_id: str,
    agent_binding: str,
    task_id: str,
    task_digest: str | None,
) -> str:
    identity = "\0".join((repository_id, agent_binding, task_id, task_digest or ""))
    return f"evt-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}"


def build_result_event(
    *,
    control_dir: Path,
    task_id: str,
    result: dict[str, Any],
    emitted_at: str | None = None,
) -> dict[str, Any]:
    if not _TASK_ID_RE.fullmatch(task_id):
        raise ValueError(f"invalid task id for result event: {task_id!r}")
    result_id = result.get("id")
    if result_id is not None and result_id != task_id:
        raise ValueError("result id does not match published task id")

    repository_id, repository, agent_binding = _load_control_identity(control_dir)
    raw_digest = result.get("task_digest")
    task_digest = raw_digest if isinstance(raw_digest, str) and _DIGEST_RE.fullmatch(raw_digest) else None
    raw_status = result.get("status")
    result_status = raw_status if isinstance(raw_status, str) and _STATUS_RE.fullmatch(raw_status) else "unknown"

    event = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_id": _event_id(repository_id, agent_binding, task_id, task_digest),
        "event_type": EVENT_TYPE_TASK_RESULT_READY,
        "emitted_at": emitted_at or now_iso(),
        "repository_id": repository_id,
        "repository": repository,
        "agent_binding": agent_binding,
        "task_id": task_id,
        "result_status": result_status,
    }
    if task_digest is not None:
        event["task_digest"] = task_digest
    return event


def _event_path(event_id: str, *, state_dir: Path | None = None) -> Path:
    if not _EVENT_ID_RE.fullmatch(event_id):
        raise ValueError(f"invalid event id: {event_id!r}")
    return outbox_dir(state_dir) / f"{event_id}.json"


def _event_timestamp(event: dict[str, Any], fallback: float) -> float:
    raw = event.get("emitted_at")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is not None:
                return parsed.timestamp()
        except ValueError:
            pass
    return fallback


def _valid_event_payload(payload: dict[str, Any]) -> bool:
    if payload.get("schema_version") != EVENT_SCHEMA_VERSION:
        return False
    if payload.get("event_type") != EVENT_TYPE_TASK_RESULT_READY:
        return False

    event_id = payload.get("event_id")
    repository_id = payload.get("repository_id")
    repository = payload.get("repository")
    task_id = payload.get("task_id")
    result_status = payload.get("result_status")
    emitted_at = payload.get("emitted_at")
    raw_digest = payload.get("task_digest")

    if not isinstance(event_id, str) or not _EVENT_ID_RE.fullmatch(event_id):
        return False
    if not isinstance(repository_id, str) or not _REPOSITORY_ID_RE.fullmatch(repository_id):
        return False
    if not isinstance(repository, str) or not _REPOSITORY_RE.fullmatch(repository):
        return False
    if not isinstance(task_id, str) or not _TASK_ID_RE.fullmatch(task_id):
        return False
    if not isinstance(result_status, str) or not _STATUS_RE.fullmatch(result_status):
        return False
    if raw_digest is not None and (
        not isinstance(raw_digest, str) or not _DIGEST_RE.fullmatch(raw_digest)
    ):
        return False
    if not isinstance(emitted_at, str) or len(emitted_at) > 64:
        return False
    try:
        parsed = datetime.fromisoformat(emitted_at)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False

    try:
        agent_binding = _canonical_binding(payload.get("agent_binding"))
    except ValueError:
        return False
    expected_id = _event_id(repository_id, agent_binding, task_id, raw_digest)
    return event_id == expected_id


def _read_event_file(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EVENT_BYTES:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not _valid_event_payload(payload):
        return None
    event_id = payload["event_id"]
    if path.name != f"{event_id}.json":
        return None
    return payload


def _same_event_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(left.get(field) == right.get(field) for field in _EVENT_IDENTITY_FIELDS)


def prune_outbox(
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> list[str]:
    directory = outbox_dir(state_dir)
    directory.mkdir(parents=True, exist_ok=True)
    reference = time.time() if now is None else now
    entries: list[tuple[float, Path]] = []
    removed: list[str] = []

    for path in directory.glob("evt-*.json"):
        event = _read_event_file(path)
        try:
            fallback = path.stat().st_mtime
        except OSError:
            continue
        timestamp = _event_timestamp(event or {}, fallback)
        if event is None or reference - timestamp > EVENT_TTL_SECONDS:
            try:
                path.unlink()
                removed.append(path.name)
            except FileNotFoundError:
                pass
            continue
        entries.append((timestamp, path))

    entries.sort(key=lambda item: (item[0], item[1].name))
    overflow = max(0, len(entries) - MAX_OUTBOX_EVENTS)
    for _, path in entries[:overflow]:
        try:
            path.unlink()
            removed.append(path.name)
        except FileNotFoundError:
            pass

    if removed:
        fsync_directory(directory)
    return removed


def enqueue_event(
    event: dict[str, Any],
    *,
    state_dir: Path | None = None,
) -> Path:
    event_id = event.get("event_id")
    if not isinstance(event_id, str):
        raise ValueError("event_id is required")
    if not _valid_event_payload(event):
        raise ValueError("invalid result event payload")
    path = _event_path(event_id, state_dir=state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    prune_outbox(state_dir=state_dir)

    encoded = json.dumps(event, indent=2, ensure_ascii=False) + "\n"
    if len(encoded.encode("utf-8")) > MAX_EVENT_BYTES:
        raise ValueError("result event exceeds bounded outbox event size")

    if path.exists():
        existing = _read_event_file(path)
        if existing is None or not _same_event_identity(existing, event):
            raise ValueError(f"event id collision for {event_id}")
        return path

    atomic_write_text(path, encoded)
    fsync_directory(path.parent)
    prune_outbox(state_dir=state_dir)
    return path


def record_published_result(
    *,
    control_dir: Path,
    task_id: str,
    result: dict[str, Any],
    state_dir: Path | None = None,
) -> dict[str, Any]:
    event = build_result_event(control_dir=control_dir, task_id=task_id, result=result)
    path = enqueue_event(event, state_dir=state_dir)
    return _read_event_file(path) or event


def pending_events(*, state_dir: Path | None = None) -> list[dict[str, Any]]:
    prune_outbox(state_dir=state_dir)
    directory = outbox_dir(state_dir)
    events: list[tuple[float, dict[str, Any]]] = []
    for path in directory.glob("evt-*.json"):
        event = _read_event_file(path)
        if event is None:
            continue
        try:
            fallback = path.stat().st_mtime
        except OSError:
            fallback = 0.0
        events.append((_event_timestamp(event, fallback), event))
    events.sort(key=lambda item: (item[0], str(item[1]["event_id"])))
    return [event for _, event in events]


def acknowledge_event(event_id: str, *, state_dir: Path | None = None) -> bool:
    path = _event_path(event_id, state_dir=state_dir)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    fsync_directory(path.parent)
    return True


def outbox_health(*, state_dir: Path | None = None) -> dict[str, Any]:
    events = pending_events(state_dir=state_dir)
    oldest_age_seconds: float | None = None
    if events:
        timestamp = _event_timestamp(events[0], time.time())
        oldest_age_seconds = max(0.0, time.time() - timestamp)
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "pending_count": len(events),
        "oldest_age_seconds": oldest_age_seconds,
    }
