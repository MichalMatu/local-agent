#!/usr/bin/env python3
"""Bounded cleanup for Git-backed Local Agent runtime metadata."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from local_agent.foundation import storage
from agent_process import termination_critical_section

TERMINAL_PAIR_RETENTION = 32
RUN_RETENTION = 32
ACK_RETENTION = 16
ORPHAN_RESULT_RETENTION = 8
_RUNTIME_PREFIXES = (
    ".agent/tasks/",
    ".agent/results/",
    ".agent/runs/",
    ".agent/daemon/acks/",
)
_TIMESTAMP_FIELDS = (
    "updated_at",
    "finished_at",
    "completed_at",
    "ended_at",
    "started_at",
    "persisted_at",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _timestamp(payload: dict[str, Any]) -> float:
    for field in _TIMESTAMP_FIELDS:
        raw = payload.get(field)
        if not isinstance(raw, str) or not raw:
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        try:
            return parsed.timestamp()
        except (OverflowError, OSError, ValueError):
            continue
    return 0.0


def _sort_key(path: Path) -> tuple[float, str]:
    return (_timestamp(_read_json(path)), path.name)


def _json_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.glob("*.json") if path.is_file())


def _relative(control: Path, path: Path) -> str:
    return path.relative_to(control).as_posix()


def control_cleanup_plan(
    control: Path,
    *,
    terminal_pair_retention: int = TERMINAL_PAIR_RETENTION,
    run_retention: int = RUN_RETENTION,
    ack_retention: int = ACK_RETENTION,
    orphan_result_retention: int = ORPHAN_RESULT_RETENTION,
) -> tuple[str, ...]:
    """Return runtime paths safe to delete without making a task replayable."""
    if min(
        terminal_pair_retention,
        run_retention,
        ack_retention,
        orphan_result_retention,
    ) < 0:
        raise ValueError("runtime retention values must be non-negative")

    tasks_dir = control / ".agent/tasks"
    results_dir = control / ".agent/results"
    runs_dir = control / ".agent/runs"
    acks_dir = control / ".agent/daemon/acks"
    control_request = control / ".agent/daemon/control.json"

    deletes: set[Path] = set()
    pending_ids: set[str] = set()
    referenced_results: set[Path] = set()
    terminal_pairs: list[tuple[tuple[float, str], Path, Path]] = []

    for task_path in _json_files(tasks_dir):
        task = _read_json(task_path)
        raw_id = task.get("id")
        task_id = raw_id if isinstance(raw_id, str) and raw_id else task_path.stem
        result_path = results_dir / f"{task_id}.json"
        if not result_path.exists() and task_id != task_path.stem:
            alias_result = results_dir / f"{task_path.stem}.json"
            if alias_result.exists():
                result_path = alias_result
        if result_path.exists():
            referenced_results.add(result_path)
            terminal_pairs.append((_sort_key(result_path), task_path, result_path))
        else:
            pending_ids.add(task_id)
            pending_ids.add(task_path.stem)

    terminal_pairs.sort(key=lambda item: item[0], reverse=True)
    for _key, task_path, result_path in terminal_pairs[terminal_pair_retention:]:
        deletes.add(task_path)
        deletes.add(result_path)

    orphan_results = [
        path for path in _json_files(results_dir) if path not in referenced_results
    ]
    orphan_results.sort(key=_sort_key, reverse=True)
    deletes.update(orphan_results[orphan_result_retention:])

    run_candidates = [
        path for path in _json_files(runs_dir) if path.stem not in pending_ids
    ]
    run_candidates.sort(key=_sort_key, reverse=True)
    deletes.update(run_candidates[run_retention:])

    protected_ack: str | None = None
    request = _read_json(control_request)
    request_id = request.get("id")
    if isinstance(request_id, str) and request_id:
        protected_ack = request_id

    ack_candidates = [
        path for path in _json_files(acks_dir) if path.stem != protected_ack
    ]
    ack_candidates.sort(key=_sort_key, reverse=True)
    deletes.update(ack_candidates[ack_retention:])

    return tuple(sorted(_relative(control, path) for path in deletes))


def prune_control_runtime(core_module: Any) -> dict[str, Any]:
    """Prune bounded terminal history and publish one atomic cleanup commit."""
    with core_module.CONTROL_GIT_LOCK:
        paths = control_cleanup_plan(core_module.CONTROL)
        if not paths:
            return {"changed": False, "deleted": 0, "paths": ()}

        with termination_critical_section():
            for relative in paths:
                target = (core_module.CONTROL / relative).resolve()
                root = core_module.CONTROL.resolve()
                if root not in target.parents:
                    raise ValueError(f"cleanup path escapes control checkout: {relative!r}")
                if not any(relative.startswith(prefix) for prefix in _RUNTIME_PREFIXES):
                    raise ValueError(f"cleanup path is outside runtime allowlist: {relative!r}")
                target.unlink(missing_ok=True)

            add = core_module.process(
                ["git", "add", "-A", "--", *paths],
                core_module.CONTROL,
                timeout=30,
                log_commands=False,
            )
            if add["exit_code"] != 0:
                raise RuntimeError(storage.git_failure_diagnostic(add))

            staged = core_module.process(
                ["git", "diff", "--cached", "--quiet", "--", *paths],
                core_module.CONTROL,
                timeout=30,
                log_commands=False,
            )
            if staged["exit_code"] == 0:
                return {"changed": False, "deleted": 0, "paths": ()}
            if staged["exit_code"] != 1:
                raise RuntimeError(storage.git_failure_diagnostic(staged))

            commit = core_module.process(
                [
                    "git",
                    "commit",
                    "-m",
                    f"Agent runtime GC: prune {len(paths)} artifacts",
                    "--",
                    *paths,
                ],
                core_module.CONTROL,
                timeout=60,
                log_commands=False,
            )
            if commit["exit_code"] != 0:
                raise RuntimeError(storage.git_failure_diagnostic(commit))

        pull = storage.run_git_with_network_retry(
            core_module,
            ["git", *storage.bounded_control_pull_args(core_module.CONTROL_BRANCH)],
            core_module.CONTROL,
            timeout=120,
            log_commands=False,
        )
        if pull["exit_code"] != 0:
            raise RuntimeError(pull["output"])

        push = storage.run_git_with_network_retry(
            core_module,
            ["git", "push", "origin", core_module.CONTROL_BRANCH],
            core_module.CONTROL,
            timeout=120,
            log_commands=False,
        )
        if push["exit_code"] != 0:
            raise RuntimeError(push["output"])

    logger = getattr(core_module, "log", None)
    if callable(logger):
        logger(f"runtime GC pruned {len(paths)} control artifacts")
    return {"changed": True, "deleted": len(paths), "paths": paths}
