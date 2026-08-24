#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import agent_core as core
import agentd
from agent_repo_admin import validate_repository
from agent_repository import RepositoryContext, load_repository_registry
from agent_runtime import idle_timeout_for, task_timeout_for
from agent_version import RELEASE_VERSION

CONTROL_HISTORY_WARNING_COMMITS = 5_000
CONTROL_HISTORY_WARNING_BYTES = 100 * 1024**2
DIAGNOSTIC_FILE_LIMIT = 100_000


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def command_status(_args: argparse.Namespace) -> int:
    payload = read_json(agentd.LOCAL_STATUS_PATH)
    if payload is None:
        print_json({"state": "unknown", "error": "status file not found"})
        return 1
    print_json(payload)
    return 0


def command_task(args: argparse.Namespace) -> int:
    paths = [agentd.LOCAL_RUNS_DIR / f"{args.task_id}.json"]
    try:
        repositories = load_repository_registry(path=agentd.multirepo_registry_path())
    except Exception:
        repositories = []
    for repository in repositories:
        if args.repository_id and repository.repository_id != args.repository_id:
            continue
        state = agentd.STATE_DIR / "repositories" / repository.repository_id
        paths.append(state / "runs" / f"{args.task_id}.json")
    matches = [payload for path in paths if (payload := read_json(path)) is not None]
    if not matches:
        print_json({"task_id": args.task_id, "state": "unknown"})
        return 1
    print_json(matches[0] if len(matches) == 1 else {"matches": matches})
    return 0


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    try:
        task = agentd.load_task_file(path)
    except Exception as exc:
        print_json({"valid": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1
    print_json(
        {
            "valid": True,
            "id": task["id"],
            "task_digest": agentd.task_digest(task),
            "command_timeout": core.command_timeout_for(task),
            "idle_timeout": idle_timeout_for(task),
            "task_timeout": task_timeout_for(task),
        }
    )
    return 0


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def _pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 2:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _bounded_tree_stats(path: Path) -> tuple[int, int, bool]:
    files = 0
    size = 0
    if not path.exists():
        return files, size, False
    for root, _directories, names in os.walk(path):
        for name in names:
            files += 1
            if files > DIAGNOSTIC_FILE_LIMIT:
                return files, size, True
            try:
                size += (Path(root) / name).lstat().st_size
            except OSError:
                pass
    return files, size, False


def _control_history(repository: RepositoryContext) -> dict[str, Any]:
    count = core.process(
        ["git", "rev-list", "--count", repository.control_branch],
        repository.control,
        timeout=30,
        log_commands=False,
    )
    commits = (
        int(str(count.get("output", "")).strip())
        if count["exit_code"] == 0 and str(count.get("output", "")).strip().isdigit()
        else None
    )
    files, size, truncated = _bounded_tree_stats(repository.control / ".git")
    return {
        "repository_id": repository.repository_id,
        "commits": commits,
        "git_bytes": size,
        "git_files": files,
        "scan_truncated": truncated,
        "warning": bool(
            (commits is not None and commits >= CONTROL_HISTORY_WARNING_COMMITS)
            or size >= CONTROL_HISTORY_WARNING_BYTES
        ),
    }


def command_doctor(_args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    checks.append(_check("self_repo", (agentd.SELF_REPO / ".git").exists(), str(agentd.SELF_REPO)))
    checks.append(_check("status_file", agentd.LOCAL_STATUS_PATH.exists(), str(agentd.LOCAL_STATUS_PATH)))

    try:
        status = read_json(agentd.LOCAL_STATUS_PATH) or {}
        pid = status.get("supervisor_pid", status.get("pid"))
        checks.append(_check("daemon_process", _pid_alive(pid), f"pid={pid}"))
    except Exception as exc:
        checks.append(_check("daemon_process", False, str(exc)))

    repositories: list[RepositoryContext] = []
    try:
        repositories = load_repository_registry(path=agentd.multirepo_registry_path())
        checks.append(_check("repository_registry", True, f"repositories={len(repositories)}"))
    except Exception as exc:
        checks.append(_check("repository_registry", False, f"{type(exc).__name__}: {exc}"))

    history: list[dict[str, Any]] = []
    checkpoint_stats: list[dict[str, Any]] = []
    pending_claims = 0
    pending_results = 0
    for repository in repositories:
        try:
            validate_repository(repository)
        except Exception as exc:
            checks.append(
                _check(
                    f"repository:{repository.repository_id}",
                    False,
                    f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        checks.append(
            _check(
                f"repository:{repository.repository_id}",
                True,
                repository.repository,
            )
        )
        state = agentd.STATE_DIR / "repositories" / repository.repository_id
        pending_claims += len(list((state / "claims").glob("*.json")))
        pending_results += len(list((state / "result-spool").glob("*.json")))
        files, size, truncated = _bounded_tree_stats(repository.checkpoints)
        checkpoint_stats.append(
            {
                "repository_id": repository.repository_id,
                "files": files,
                "bytes": size,
                "scan_truncated": truncated,
            }
        )
        control = _control_history(repository)
        history.append(control)
        if control["warning"]:
            warnings.append(
                f"control history is large for {repository.repository_id}: "
                f"commits={control['commits']} bytes={control['git_bytes']}"
            )

    ok = all(item["ok"] for item in checks)
    print_json(
        {
            "ok": ok,
            "release_version": RELEASE_VERSION,
            "checks": checks,
            "pending_claims": pending_claims,
            "pending_result_publications": pending_results,
            "checkpoint_stats": checkpoint_stats,
            "control_history": history,
            "warnings": warnings,
        }
    )
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Agent control and diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="show local daemon status")
    status.set_defaults(func=command_status)

    task = sub.add_parser("task", help="show local task progress")
    task.add_argument("task_id")
    task.add_argument("--repository-id")
    task.set_defaults(func=command_task)

    validate = sub.add_parser("validate-task", help="validate a task JSON file")
    validate.add_argument("path")
    validate.set_defaults(func=command_validate)

    doctor = sub.add_parser("doctor", help="run daemon installation checks")
    doctor.set_defaults(func=command_doctor)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
