from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Any

from agent_binding import canonical_agent_binding
from agent_config import TIMEOUTS

_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_RESOURCE_RE = re.compile(r"^[a-z0-9._:-]+$")
DEFAULT_IDLE_TIMEOUT = TIMEOUTS.idle_default
MAX_IDLE_TIMEOUT = TIMEOUTS.idle_max
DEFAULT_TASK_TIMEOUT = TIMEOUTS.task_default
MAX_TASK_TIMEOUT = TIMEOUTS.task_max
TASK_FINALIZATION_RESERVE = 60
DEFAULT_MEMORY_LIMIT_MB = 4096
MAX_MEMORY_LIMIT_MB = 16384
MAX_TASK_RESOURCES = 8

MAX_TASK_FILE_BYTES = 4 * 1024 * 1024
MAX_TASK_LIST_ITEMS = 256
MAX_COMMAND_CHARS = 32_768
MAX_PATCH_BYTES = 2 * 1024 * 1024
MAX_WRITE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_WRITE_BYTES = 8 * 1024 * 1024
MAX_TASK_PATH_CHARS = 1024


def task_digest(task: dict[str, Any]) -> str:
    payload = json.dumps(
        task,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def task_agent_binding(
    task: dict[str, Any],
    *,
    required: bool = False,
) -> str | None:
    raw = task.get("agent_binding")
    if raw is None:
        if required:
            raise ValueError("agent_binding is required")
        return None
    return canonical_agent_binding(raw)


def require_task_agent_binding(task: dict[str, Any], expected_agent_binding: str) -> str:
    expected = canonical_agent_binding(expected_agent_binding, field="expected_agent_binding")
    provided = task_agent_binding(task, required=True)
    assert provided is not None
    if not secrets.compare_digest(provided, expected):
        raise ValueError(
            f"agent_binding mismatch: expected {expected}, got {provided}"
        )
    return provided


def task_resources_for(task: dict[str, Any]) -> tuple[str, ...]:
    if "resources" not in task:
        raise ValueError("resources must be declared explicitly")
    raw = task["resources"]
    if not isinstance(raw, list):
        raise ValueError("resources must be a list")
    if len(raw) > MAX_TASK_RESOURCES:
        raise ValueError(f"resources exceeds {MAX_TASK_RESOURCES} items")

    resources: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("resources items must be strings")
        if not item or item != item.strip() or item != item.casefold():
            raise ValueError(f"resource must be canonical lowercase text: {item!r}")
        if not _RESOURCE_RE.fullmatch(item):
            raise ValueError(f"invalid resource name: {item!r}")
        if item in seen:
            raise ValueError(f"duplicate resource: {item!r}")
        seen.add(item)
        resources.append(item)

    if "machine" in seen and len(resources) != 1:
        raise ValueError("resource 'machine' must be declared alone")
    return tuple(resources)


def validate_task(task: dict[str, Any], *, require_agent_binding: bool = False) -> None:
    if not isinstance(task, dict):
        raise ValueError("task must be an object")
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id or len(task_id) > 200:
        raise ValueError("task id must be a non-empty string up to 200 characters")
    if not _TASK_ID_RE.fullmatch(task_id):
        raise ValueError("task id contains unsupported characters")
    task_agent_binding(task, required=require_agent_binding)
    mode = task.get("mode", "commands")
    if not isinstance(mode, str) or mode != "commands":
        raise ValueError("only mode=commands is supported")
    if "allow_write" in task and not isinstance(task["allow_write"], bool):
        raise ValueError("allow_write must be a boolean")
    if "work_branch" in task and not isinstance(task["work_branch"], str):
        raise ValueError("work_branch must be a string")
    task_resources_for(task)
    patch = task.get("patch")
    if patch is not None:
        if not isinstance(patch, str):
            raise ValueError("patch must be a string")
        if len(patch.encode("utf-8")) > MAX_PATCH_BYTES:
            raise ValueError(f"patch exceeds {MAX_PATCH_BYTES} bytes")
    for field in (
        "writes",
        "deletes",
        "commands",
        "verify_commands",
        "steps",
        "verify_steps",
    ):
        if field in task and not isinstance(task[field], list):
            raise ValueError(f"{field} must be a list")
        if len(task.get(field, [])) > MAX_TASK_LIST_ITEMS:
            raise ValueError(f"{field} exceeds {MAX_TASK_LIST_ITEMS} items")

    total_write_bytes = 0
    for item in task.get("writes", []):
        if not isinstance(item, dict):
            raise ValueError("writes items must be objects")
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not path or len(path) > MAX_TASK_PATH_CHARS:
            raise ValueError("write path must be a non-empty bounded string")
        if not isinstance(content, str):
            raise ValueError(f"write content must be a string for {path!r}")
        write_bytes = len(content.encode("utf-8"))
        if write_bytes > MAX_WRITE_BYTES:
            raise ValueError(f"write content for {path!r} exceeds {MAX_WRITE_BYTES} bytes")
        total_write_bytes += write_bytes
    if total_write_bytes > MAX_TOTAL_WRITE_BYTES:
        raise ValueError(f"writes exceed {MAX_TOTAL_WRITE_BYTES} total bytes")

    for path in task.get("deletes", []):
        if not isinstance(path, str) or not path or len(path) > MAX_TASK_PATH_CHARS:
            raise ValueError("delete paths must be non-empty bounded strings")

    for field in ("commands", "verify_commands"):
        for command in task.get(field, []):
            if not isinstance(command, str) or not command.strip():
                raise ValueError(f"{field} items must be non-empty strings")
            if len(command) > MAX_COMMAND_CHARS:
                raise ValueError(f"{field} item exceeds {MAX_COMMAND_CHARS} characters")

    for field in ("steps", "verify_steps"):
        for item in task.get(field, []):
            if not isinstance(item, dict):
                raise ValueError(f"{field} items must be objects")
            command = item.get("command")
            if isinstance(command, str) and len(command) > MAX_COMMAND_CHARS:
                raise ValueError(f"{field} item command exceeds {MAX_COMMAND_CHARS} characters")
    core_module = __import__("agent_core")
    stage_plan = core_module.stage_plan_for(task)
    command_timeout = core_module.command_timeout_for(task)
    idle_timeout_for(task)
    task_timeout = task_timeout_for(task)
    memory_limit_for(task)
    for stage in stage_plan:
        stage_timeout = int(stage.get("stage_timeout", command_timeout))
        if stage_timeout + TASK_FINALIZATION_RESERVE > task_timeout:
            raise ValueError(
                f"stage {stage['stage_name']!r} timeout {stage_timeout}s cannot fit "
                f"inside task_timeout={task_timeout}s with "
                f"{TASK_FINALIZATION_RESERVE}s finalization reserve"
            )


def _bounded_int(
    task: dict[str, Any],
    field: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw = task.get(field, default)
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ValueError(f"invalid {field}: {raw!r}") from None
    value = raw
    if value < minimum or value > maximum:
        raise ValueError(f"{field} must be {minimum}..{maximum}, got {value}")
    return value


def idle_timeout_for(task: dict[str, Any]) -> int:
    return _bounded_int(task, "idle_timeout", DEFAULT_IDLE_TIMEOUT, 0, MAX_IDLE_TIMEOUT)


def task_timeout_for(task: dict[str, Any]) -> int:
    return _bounded_int(task, "task_timeout", DEFAULT_TASK_TIMEOUT, 1, MAX_TASK_TIMEOUT)


def memory_limit_for(task: dict[str, Any]) -> int:
    return _bounded_int(
        task,
        "memory_limit_mb",
        DEFAULT_MEMORY_LIMIT_MB,
        0,
        MAX_MEMORY_LIMIT_MB,
    )
