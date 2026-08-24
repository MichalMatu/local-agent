#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import agent_core as core
import agentd
from agent_repository import RepositoryContext, load_repository_registry

MULTIREPO_DAEMON_VERSION = "4.6.0-staging"
WORKER_IDLE = 0
WORKER_PROCESSED = 10
_CONTROL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def repository_state_dir(repository: RepositoryContext) -> Path:
    return agentd.STATE_DIR / "repositories" / repository.repository_id


def bind_repository(repository: RepositoryContext) -> None:
    """Bind legacy core/daemon globals inside this short-lived worker process only."""
    core.CONTROL = repository.control
    core.WORK = repository.work
    core.CHECKPOINTS = repository.checkpoints
    core.CONTROL_BRANCH = repository.control_branch

    state_dir = repository_state_dir(repository)
    agentd.CLAIMS_DIR = state_dir / "claims"
    agentd.CORRUPT_CLAIMS_DIR = state_dir / "corrupt-claims"
    agentd.LOCAL_STATUS_PATH = state_dir / "status.json"
    agentd.LOCAL_RUNS_DIR = state_dir / "runs"


def validate_repository_checkouts(repository: RepositoryContext) -> None:
    missing: list[str] = []
    if not (repository.control / ".git").exists():
        missing.append(f"control checkout missing: {repository.control}")
    if not (repository.work / ".git").exists():
        missing.append(f"work checkout missing: {repository.work}")
    if missing:
        raise RuntimeError("; ".join(missing))


def repository_status_fields(repository: RepositoryContext) -> dict[str, Any]:
    fields: dict[str, Any] = {
        **repository.status_fields(),
        "execution_model": "multi_repository_worker",
        "worker_pid": os.getpid(),
    }
    supervisor_pid = os.environ.get("LOCAL_AGENT_SUPERVISOR_PID")
    if supervisor_pid:
        try:
            fields["supervisor_pid"] = int(supervisor_pid)
        except ValueError:
            fields["supervisor_pid"] = supervisor_pid
    return fields


def _previous_repository_status() -> tuple[str | None, float | None]:
    path = agentd.LOCAL_STATUS_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        state = str(payload.get("state", "")) or None
        return state, path.stat().st_mtime
    except (FileNotFoundError, json.JSONDecodeError, OSError, AttributeError):
        return None, None


def publish_repository_status(
    repository: RepositoryContext,
    state: str,
    *,
    force_remote: bool = True,
    **extra: Any,
) -> None:
    """Persist every local status but throttle idle remote commits across worker processes."""
    previous_state, previous_mtime = _previous_repository_status()
    payload = agentd.daemon_status_payload(
        state,
        **repository_status_fields(repository),
        **extra,
    )
    agentd.atomic_write_json(agentd.LOCAL_STATUS_PATH, payload)

    now = time.time()
    remote_due = (
        force_remote
        or previous_state != state
        or previous_mtime is None
        or now - previous_mtime >= agentd.REMOTE_HEARTBEAT_SECONDS
    )
    if not remote_due:
        return
    try:
        agentd.publish_control_json(
            agentd.REMOTE_DAEMON_STATUS,
            payload,
            commit_message=f"Agent repository status: {repository.repository_id} {state}",
        )
    except Exception as exc:
        core.log(
            f"remote repository status publish failed repository={repository.repository_id}: "
            f"{type(exc).__name__}: {exc}"
        )


def _control_ack_path(control_id: str) -> Path:
    return core.CONTROL / agentd.REMOTE_CONTROL_ACK_DIR / f"{control_id}.json"


def publish_repository_control_ack(
    repository: RepositoryContext,
    control_id: str,
    action: str,
    status: str,
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {
        "id": control_id,
        "action": action,
        "status": status,
        "daemon_version": MULTIREPO_DAEMON_VERSION,
        "updated_at": agentd.now_iso(),
        **repository.status_fields(),
        **extra,
    }
    agentd.publish_control_json(
        f"{agentd.REMOTE_CONTROL_ACK_DIR}/{control_id}.json",
        payload,
        commit_message=f"Agent repository control ack: {control_id}",
    )


def handle_repository_control(repository: RepositoryContext) -> None:
    """Handle only controls that are safe inside a short-lived repository worker."""
    path = core.CONTROL / agentd.REMOTE_CONTROL_REQUEST
    if not path.exists():
        return
    try:
        request = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        core.log(f"invalid repository control request: {type(exc).__name__}: {exc}")
        return
    if not isinstance(request, dict):
        core.log("invalid repository control request: root must be an object")
        return

    control_id = str(request.get("id", ""))
    action = str(request.get("action", ""))
    if (
        not control_id
        or len(control_id) > 120
        or not _CONTROL_ID_RE.fullmatch(control_id)
        or _control_ack_path(control_id).exists()
    ):
        return

    if action == "status":
        publish_repository_status(
            repository,
            "idle",
            force_remote=True,
            control_id=control_id,
        )
        publish_repository_control_ack(
            repository,
            control_id,
            action,
            "completed",
            result="status_published",
        )
        return

    if action in {"restart", "self_update"}:
        publish_repository_control_ack(
            repository,
            control_id,
            action,
            "rejected",
            result="supervisor_action_not_supported_in_repository_worker",
        )
        return

    publish_repository_control_ack(
        repository,
        control_id,
        action,
        "rejected",
        result="unsupported_action",
    )


def poll_repository_once(repository: RepositoryContext) -> bool:
    """Poll one repository and execute at most one task."""
    bind_repository(repository)
    validate_repository_checkouts(repository)
    previous_version = agentd.DAEMON_VERSION
    agentd.DAEMON_VERSION = MULTIREPO_DAEMON_VERSION
    try:
        core.log(
            f"multi-repo poll repository={repository.repository_id} "
            f"remote={repository.repository}"
        )
        core.sync_control()
        agentd.recover_stale_claims()
        agentd.recover_invalid_task_files()
        handle_repository_control(repository)
        pending = agentd.pending_tasks()
        if not pending:
            publish_repository_status(
                repository,
                "idle",
                force_remote=False,
            )
            return False

        _, task = pending[0]
        core.log(
            f"multi-repo dispatch repository={repository.repository_id} "
            f"task={task.get('id')}"
        )
        agentd.execute_task(task)
        publish_repository_status(
            repository,
            "idle",
            force_remote=True,
            last_task_id=str(task.get("id", "")),
        )
        return True
    finally:
        agentd.DAEMON_VERSION = previous_version


def repository_by_id(
    repository_id: str,
    *,
    registry_path: Path | None,
) -> RepositoryContext:
    repositories = load_repository_registry(path=registry_path)
    for repository in repositories:
        if repository.repository_id == repository_id:
            return repository
    raise ValueError(f"repository id is not enabled: {repository_id!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll one configured local-agent repository once.")
    parser.add_argument("--repository-id", required=True)
    parser.add_argument("--registry", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = repository_by_id(args.repository_id, registry_path=args.registry)
    processed = poll_repository_once(repository)
    return WORKER_PROCESSED if processed else WORKER_IDLE


if __name__ == "__main__":
    raise SystemExit(main())
