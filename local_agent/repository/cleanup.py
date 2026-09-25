#!/usr/bin/env python3
"""Bounded cleanup for Git-backed Local Agent runtime metadata."""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from local_agent.foundation import storage
from local_agent.foundation.process import RESOURCE_LEASE_FDS_ENV, termination_critical_section

TERMINAL_PAIR_RETENTION = 32
RUN_RETENTION = 32
ACK_RETENTION = 16
ORPHAN_RESULT_RETENTION = 8
CONTROL_HISTORY_COMPACTION_THRESHOLD = storage.CONTROL_HISTORY_DEPTH
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


def _control_git_environment(core_module: Any) -> Mapping[str, str] | None:
    """Keep repository leases but exclude task-resource FDs from runtime-GC Git."""
    raw = getattr(core_module, "ENV", None)
    if not isinstance(raw, Mapping):
        return None
    environment = dict(raw)
    environment.pop(RESOURCE_LEASE_FDS_ENV, None)
    return environment


def _control_process(
    core_module: Any,
    args: list[str],
    *,
    timeout: int,
    log_commands: bool,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "timeout": timeout,
        "log_commands": log_commands,
    }
    environment = _control_git_environment(core_module)
    if environment is not None:
        kwargs["environment"] = environment
    return core_module.process(args, core_module.CONTROL, **kwargs)


def _require_control_git(result: dict[str, Any], operation: str) -> str:
    if result["exit_code"] != 0:
        raise RuntimeError(f"{operation} failed: {storage.git_failure_diagnostic(result)}")
    return str(result.get("output", "")).strip()


def _control_output(
    core_module: Any,
    args: list[str],
    operation: str,
    *,
    timeout: int = 30,
) -> str:
    return _require_control_git(
        _control_process(
            core_module,
            ["git", *args],
            timeout=timeout,
            log_commands=False,
        ),
        operation,
    )


def _parse_remote_branch_sha(output: str, branch: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(
            f"expected exactly one remote ref for {branch!r}, got {len(lines)}"
        )
    fields = lines[0].split()
    expected_ref = f"refs/heads/{branch}"
    if len(fields) < 2 or fields[1] != expected_ref:
        raise RuntimeError(f"unexpected ls-remote output for {branch!r}: {lines[0]!r}")
    return fields[0]


def _remote_control_sha(core_module: Any) -> str:
    branch = core_module.CONTROL_BRANCH
    environment = _control_git_environment(core_module)
    result = storage.run_git_with_network_retry(
        core_module,
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
        core_module.CONTROL,
        timeout=120,
        log_commands=False,
        environment=environment,
    )
    output = _require_control_git(result, "read remote control branch")
    return _parse_remote_branch_sha(output, branch)


def _realign_compacted_control_checkout(
    core_module: Any,
    *,
    new_sha: str,
    tree_sha: str,
) -> None:
    branch = core_module.CONTROL_BRANCH
    reset = _control_process(
        core_module,
        ["git", "reset", "--hard", new_sha],
        timeout=120,
        log_commands=False,
    )
    _require_control_git(reset, "reset compacted control checkout")
    update_ref = _control_process(
        core_module,
        ["git", "update-ref", f"refs/remotes/origin/{branch}", new_sha],
        timeout=30,
        log_commands=False,
    )
    _require_control_git(update_ref, "update compacted remote-tracking ref")

    final_head = _control_output(core_module, ["rev-parse", "HEAD"], "verify compacted HEAD")
    final_tree = _control_output(
        core_module,
        ["rev-parse", "HEAD^{tree}"],
        "verify compacted control tree",
    )
    if final_head != new_sha:
        raise RuntimeError("local control checkout did not converge on compacted root")
    if final_tree != tree_sha:
        raise RuntimeError("local control tree changed during history compaction")


def _compact_control_history_locked(
    core_module: Any,
    *,
    threshold: int = CONTROL_HISTORY_COMPACTION_THRESHOLD,
) -> dict[str, Any]:
    """Bound remote control history while preserving the exact current tree.

    Caller must hold CONTROL_GIT_LOCK. The force push is never blindly retried: an
    ambiguous transport failure is reconciled against the remote ref first.
    """
    if threshold < 1:
        raise ValueError("control history compaction threshold must be positive")

    dirty = _control_output(
        core_module,
        ["status", "--porcelain=v1", "--untracked-files=all"],
        "inspect control checkout",
    )
    if dirty:
        return {"changed": False, "reason": "dirty"}

    branch = _control_output(
        core_module,
        ["symbolic-ref", "--quiet", "--short", "HEAD"],
        "read control branch",
    )
    if branch != core_module.CONTROL_BRANCH:
        return {"changed": False, "reason": "wrong_branch", "branch": branch}

    visible_raw = _control_output(
        core_module,
        ["rev-list", "--count", "HEAD"],
        "count visible control commits",
    )
    try:
        visible_commits = int(visible_raw)
    except ValueError as exc:
        raise RuntimeError(f"invalid control commit count: {visible_raw!r}") from exc
    if visible_commits < threshold:
        return {
            "changed": False,
            "reason": "below_threshold",
            "visible_commits": visible_commits,
            "threshold": threshold,
        }

    old_sha = _control_output(core_module, ["rev-parse", "HEAD"], "read control HEAD")
    remote_sha = _remote_control_sha(core_module)
    if old_sha != remote_sha:
        return {
            "changed": False,
            "reason": "remote_changed",
            "head_sha": old_sha,
            "remote_sha": remote_sha,
        }

    tree_sha = _control_output(
        core_module,
        ["rev-parse", "HEAD^{tree}"],
        "read control tree",
    )
    new_sha = _control_output(
        core_module,
        ["commit-tree", tree_sha, "-m", "Compact local-agent control history"],
        "create compacted control root commit",
        timeout=60,
    )
    new_tree = _control_output(
        core_module,
        ["rev-parse", f"{new_sha}^{{tree}}"],
        "verify compacted root tree",
    )
    if new_tree != tree_sha:
        raise RuntimeError(
            "compacted control tree differs from source tree; refusing remote update"
        )

    lease = f"--force-with-lease=refs/heads/{branch}:{old_sha}"
    push = _control_process(
        core_module,
        ["git", "push", lease, "origin", f"{new_sha}:refs/heads/{branch}"],
        timeout=120,
        log_commands=False,
    )
    push_succeeded = push["exit_code"] == 0
    if not push_succeeded:
        observed_remote = _remote_control_sha(core_module)
        if observed_remote != new_sha:
            return {
                "changed": False,
                "reason": "lease_or_push_failed",
                "old_sha": old_sha,
                "new_sha": new_sha,
                "remote_sha": observed_remote,
                "diagnostic": storage.git_failure_diagnostic(push),
            }

    _realign_compacted_control_checkout(
        core_module,
        new_sha=new_sha,
        tree_sha=tree_sha,
    )
    return {
        "changed": True,
        "old_sha": old_sha,
        "new_sha": new_sha,
        "tree_sha": tree_sha,
        "visible_commits_before": visible_commits,
        "push_reconciled": not push_succeeded,
    }


def compact_control_history(
    core_module: Any,
    *,
    threshold: int = CONTROL_HISTORY_COMPACTION_THRESHOLD,
) -> dict[str, Any]:
    """Public lock-safe control-history compaction entry point."""
    with core_module.CONTROL_GIT_LOCK:
        return _compact_control_history_locked(core_module, threshold=threshold)


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
    """Prune runtime artifacts and keep remote control history bounded."""
    paths: tuple[str, ...] = ()
    with core_module.CONTROL_GIT_LOCK:
        paths = control_cleanup_plan(core_module.CONTROL)
        if paths:
            with termination_critical_section():
                for relative in paths:
                    target = (core_module.CONTROL / relative).resolve()
                    root = core_module.CONTROL.resolve()
                    if root not in target.parents:
                        raise ValueError(f"cleanup path escapes control checkout: {relative!r}")
                    if not any(relative.startswith(prefix) for prefix in _RUNTIME_PREFIXES):
                        raise ValueError(f"cleanup path is outside runtime allowlist: {relative!r}")
                    target.unlink(missing_ok=True)

                add = _control_process(
                    core_module,
                    ["git", "add", "-A", "--", *paths],
                    timeout=30,
                    log_commands=False,
                )
                if add["exit_code"] != 0:
                    raise RuntimeError(storage.git_failure_diagnostic(add))

                staged = _control_process(
                    core_module,
                    ["git", "diff", "--cached", "--quiet", "--", *paths],
                    timeout=30,
                    log_commands=False,
                )
                if staged["exit_code"] not in {0, 1}:
                    raise RuntimeError(storage.git_failure_diagnostic(staged))

                if staged["exit_code"] == 1:
                    commit = _control_process(
                        core_module,
                        [
                            "git",
                            "commit",
                            "-m",
                            f"Agent runtime GC: prune {len(paths)} artifacts",
                            "--",
                            *paths,
                        ],
                        timeout=60,
                        log_commands=False,
                    )
                    if commit["exit_code"] != 0:
                        raise RuntimeError(storage.git_failure_diagnostic(commit))

                    environment = _control_git_environment(core_module)
                    pull = storage.run_git_with_network_retry(
                        core_module,
                        ["git", *storage.bounded_control_pull_args(core_module.CONTROL_BRANCH)],
                        core_module.CONTROL,
                        timeout=120,
                        log_commands=False,
                        environment=environment,
                    )
                    if pull["exit_code"] != 0:
                        raise RuntimeError(pull["output"])

                    push = storage.run_git_with_network_retry(
                        core_module,
                        ["git", "push", "origin", core_module.CONTROL_BRANCH],
                        core_module.CONTROL,
                        timeout=120,
                        log_commands=False,
                        environment=environment,
                    )
                    if push["exit_code"] != 0:
                        raise RuntimeError(push["output"])

        try:
            history = _compact_control_history_locked(core_module)
        except Exception as exc:
            history = {
                "changed": False,
                "reason": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    logger = getattr(core_module, "log", None)
    if callable(logger):
        if paths:
            logger(f"runtime GC pruned {len(paths)} control artifacts")
        if history.get("changed"):
            logger(
                "runtime GC compacted control history "
                f"from {history['visible_commits_before']} visible commits"
            )
        elif history.get("reason") == "error":
            logger(f"control history compaction skipped: {history['error']}")

    return {
        "changed": bool(paths) or bool(history.get("changed")),
        "deleted": len(paths),
        "paths": paths,
        "history": history,
    }
