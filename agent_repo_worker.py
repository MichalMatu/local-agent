#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import signal
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import agent_core as core
import agent_storage as storage
import agentd
from agent_process import (
    ExecutionLeaseBusy,
    LEASE_KEYS_DIGEST_ENV,
    acquire_execution_leases,
    defer_termination,
    execution_lease_path,
    inherited_lease_fds,
    lease_keys_digest,
)
from agent_repository import (
    RepositoryContext,
    load_repository_registry,
    repository_config_digest,
    repository_lease_keys,
)
from agent_version import RELEASE_VERSION

MULTIREPO_DAEMON_VERSION = RELEASE_VERSION
WORKER_IDLE = 0
WORKER_PROCESSED = 10
WORKER_BUSY = 11
WORKER_CONFIG_CHANGED = 12
_CONTROL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def repository_state_dir(repository: RepositoryContext) -> Path:
    return agentd.STATE_DIR / "repositories" / repository.repository_id


def repository_lease_dir() -> Path:
    return agentd.STATE_DIR / "locks" / "repositories"


def _validate_inherited_repository_leases(repository: RepositoryContext) -> bool:
    fds = inherited_lease_fds(os.environ)
    if not fds:
        return False
    keys = repository_lease_keys(repository)
    expected_digest = lease_keys_digest(keys)
    if os.environ.get(LEASE_KEYS_DIGEST_ENV) != expected_digest:
        raise RuntimeError("inherited repository lease identity mismatch")
    paths = tuple(execution_lease_path(repository_lease_dir(), key) for key in keys)
    if len(fds) != len(paths):
        raise RuntimeError("inherited repository lease descriptor count mismatch")
    for fd, path in zip(fds, paths, strict=True):
        try:
            descriptor_stat = os.fstat(fd)
            path_stat = path.stat()
        except OSError as exc:
            raise RuntimeError("inherited repository lease is unavailable") from exc
        if (descriptor_stat.st_dev, descriptor_stat.st_ino) != (
            path_stat.st_dev,
            path_stat.st_ino,
        ):
            raise RuntimeError("inherited repository lease file mismatch")
    return True


@contextlib.contextmanager
def repository_execution_lease(repository: RepositoryContext) -> Iterator[None]:
    """Hold every stable identity lock for one complete repository turn."""
    if _validate_inherited_repository_leases(repository):
        yield
        return

    leases = acquire_execution_leases(
        repository_lease_dir(),
        repository_lease_keys(repository),
    )
    updates = leases.environment()
    previous_os = {name: os.environ.get(name) for name in updates}
    previous_core = {name: core.ENV.get(name) for name in updates}
    os.environ.update(updates)
    core.ENV.update(updates)
    try:
        yield
    finally:
        for target, previous in ((os.environ, previous_os), (core.ENV, previous_core)):
            for name, value in previous.items():
                if value is None:
                    target.pop(name, None)
                else:
                    target[name] = value
        leases.close()


def shutdown_handler(signum: int, _frame: Any) -> None:
    if defer_termination(signum):
        return
    core.log(f"received signal {signum}; terminating worker subprocesses")
    agentd.shutdown_runtime_processes()
    raise SystemExit(128 + signum)


def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)


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
    agentd.RESULT_SPOOL_DIR = state_dir / "result-spool"


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


def sync_control_quietly() -> None:
    """Run bounded routine control-branch sync without printing low-level Git commands."""
    with contextlib.redirect_stdout(io.StringIO()):
        storage.sync_control(core)


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
        # These are global supervisor actions. A fast per-repository worker must
        # leave them unacknowledged so the supervisor can own the request.
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
        sync_control_quietly()
        agentd.recover_stale_claims()
        agentd.recover_invalid_task_files()
        handle_repository_control(repository)
        pending = agentd.pending_tasks()
        if not pending:
            state = "publication_pending" if agentd.has_pending_publications() else "idle"
            publish_repository_status(
                repository,
                state,
                force_remote=False,
            )
            return False

        _, task = pending[0]
        core.log(
            f"multi-repo dispatch repository={repository.repository_id} "
            f"task={task.get('id')}"
        )
        outcome = agentd.execute_task(
            task,
            remote_daemon_status=False,
            remote_result_published=False,
        )
        state = "publication_pending" if outcome == "publication_pending" else "idle"
        publish_repository_status(
            repository,
            state,
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
    expected_config_digest: str,
) -> RepositoryContext:
    repositories = load_repository_registry(path=registry_path)
    for repository in repositories:
        if repository.repository_id == repository_id:
            if repository_config_digest(repository) != expected_config_digest:
                raise ValueError(
                    f"repository configuration changed before worker start: "
                    f"{repository_id!r}"
                )
            return repository
    raise ValueError(f"repository id is not enabled: {repository_id!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll one configured local-agent repository once.")
    parser.add_argument("--repository-id", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--expected-config-digest", required=True)
    return parser.parse_args()


def main() -> int:
    install_signal_handlers()
    args = parse_args()
    try:
        repository = repository_by_id(
            args.repository_id,
            registry_path=args.registry,
            expected_config_digest=args.expected_config_digest,
        )
    except ValueError as exc:
        core.log(str(exc))
        return WORKER_CONFIG_CHANGED
    try:
        with repository_execution_lease(repository):
            processed = poll_repository_once(repository)
    except ExecutionLeaseBusy as exc:
        core.log(
            f"repository execution lease busy repository={repository.repository_id} "
            f"key={exc.key}"
        )
        return WORKER_BUSY
    return WORKER_PROCESSED if processed else WORKER_IDLE


if __name__ == "__main__":
    raise SystemExit(main())
