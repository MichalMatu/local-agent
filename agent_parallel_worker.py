#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import fcntl
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

import agent_core as core
import agentd
import agent_repo_worker as serial_worker
from agent_process import (
    ExecutionLeaseBusy,
    LEASE_FDS_ENV,
    execution_lease_path,
)
from agent_repository import RepositoryContext
from agent_runtime import memory_limit_for

WORKER_RESOURCE_BUSY = 13
WORKER_MACHINE_BUSY = 14
MAX_TASK_RESOURCES = 8
MAX_PARALLEL_TASK_MEMORY_MB = 1024
PARALLEL_DAEMON_VERSION = serial_worker.MULTIREPO_DAEMON_VERSION
_RESOURCE_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


class MachineResourceBusy(RuntimeError):
    def __init__(self, resource: str) -> None:
        super().__init__(f"machine resource is busy: {resource}")
        self.resource = resource


def resource_lock_dir() -> Path:
    return agentd.STATE_DIR / "locks" / "machine-resources"


def task_resources(task: dict[str, object]) -> tuple[str, ...]:
    """Return effective resources with conservative legacy and memory fallbacks."""
    if "resources" not in task:
        return ("machine",)

    raw = task.get("resources")
    if not isinstance(raw, list) or len(raw) > MAX_TASK_RESOURCES:
        return ("machine",)

    normalized: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            return ("machine",)
        value = item.strip().casefold()
        if not value or not _RESOURCE_RE.fullmatch(value):
            return ("machine",)
        normalized.add(value)

    if "machine" in normalized:
        return ("machine",)

    try:
        memory_limit = memory_limit_for(task)
    except (TypeError, ValueError):
        return ("machine",)
    if memory_limit == 0 or memory_limit > MAX_PARALLEL_TASK_MEMORY_MB:
        return ("machine",)

    return tuple(sorted(normalized))


def _acquire_flock(
    handle: TextIO,
    operation: int,
    *,
    resource: str,
) -> None:
    try:
        fcntl.flock(handle.fileno(), operation | fcntl.LOCK_NB)
    except BlockingIOError:
        raise MachineResourceBusy(resource) from None


def _restore_env_value(target: dict[str, str], name: str, previous: str | None) -> None:
    if previous is None:
        target.pop(name, None)
    else:
        target[name] = previous


@contextlib.contextmanager
def _inherit_resource_fds(handles: list[TextIO]) -> Iterator[None]:
    existing_raw = os.environ.get(LEASE_FDS_ENV, "").strip()
    existing = [item for item in existing_raw.split(",") if item]
    combined = existing + [str(handle.fileno()) for handle in handles]
    value = ",".join(dict.fromkeys(combined))

    previous_os = os.environ.get(LEASE_FDS_ENV)
    previous_core = core.ENV.get(LEASE_FDS_ENV)
    os.environ[LEASE_FDS_ENV] = value
    core.ENV[LEASE_FDS_ENV] = value
    try:
        yield
    finally:
        _restore_env_value(os.environ, LEASE_FDS_ENV, previous_os)
        _restore_env_value(core.ENV, LEASE_FDS_ENV, previous_core)


@contextlib.contextmanager
def machine_resource_lease(task: dict[str, object]) -> Iterator[tuple[str, ...]]:
    """Acquire machine resources without waiting on a stale, unclaimed task copy."""
    resources = task_resources(task)
    lock_dir = resource_lock_dir()
    lock_dir.mkdir(parents=True, exist_ok=True)

    gate = (lock_dir / "arbitration-gate.lock").open("a+", encoding="utf-8")
    machine = (lock_dir / "machine.lock").open("a+", encoding="utf-8")
    resource_handles: list[TextIO] = []
    try:
        _acquire_flock(gate, fcntl.LOCK_EX, resource="arbitration-gate")
        machine_mode = fcntl.LOCK_EX if resources == ("machine",) else fcntl.LOCK_SH
        _acquire_flock(machine, machine_mode, resource="machine")

        if resources != ("machine",):
            for resource in resources:
                path = execution_lease_path(lock_dir, f"resource:{resource}")
                handle = path.open("a+", encoding="utf-8")
                try:
                    _acquire_flock(handle, fcntl.LOCK_EX, resource=resource)
                except BaseException:
                    handle.close()
                    raise
                resource_handles.append(handle)

        fcntl.flock(gate.fileno(), fcntl.LOCK_UN)
        gate.close()

        inherited = [machine, *resource_handles]
        with _inherit_resource_fds(inherited):
            yield resources
    finally:
        for handle in reversed(resource_handles):
            with contextlib.suppress(OSError):
                handle.close()
        with contextlib.suppress(OSError):
            machine.close()
        if not gate.closed:
            with contextlib.suppress(OSError):
                gate.close()


def poll_repository_once(repository: RepositoryContext) -> bool:
    """Poll one repository and execute at most one resource-arbitrated task."""
    serial_worker.bind_repository(repository)
    serial_worker.validate_repository_checkouts(repository)
    previous_version = agentd.DAEMON_VERSION
    agentd.DAEMON_VERSION = PARALLEL_DAEMON_VERSION
    try:
        serial_worker.sync_control_quietly()
        agentd.recover_stale_claims()
        agentd.recover_invalid_task_files()
        serial_worker.handle_repository_control(repository)
        pending = agentd.pending_tasks()
        if not pending:
            state = "publication_pending" if agentd.has_pending_publications() else "idle"
            serial_worker.publish_repository_status(
                repository,
                state,
                force_remote=False,
                execution_variant="parallel",
            )
            return False

        _, task = pending[0]
        with machine_resource_lease(task) as resources:
            core.log(
                f"[parallel] TASK START repository={repository.repository_id} "
                f"task={task.get('id')} resources={list(resources)}"
            )
            outcome = agentd.execute_task(
                task,
                remote_daemon_status=False,
                remote_result_published=False,
            )

        state = "publication_pending" if outcome == "publication_pending" else "idle"
        serial_worker.publish_repository_status(
            repository,
            state,
            force_remote=True,
            last_task_id=str(task.get("id", "")),
            execution_variant="parallel",
        )
        return True
    finally:
        agentd.DAEMON_VERSION = previous_version


def main() -> int:
    serial_worker.install_signal_handlers()
    args = serial_worker.parse_args()
    try:
        repository = serial_worker.repository_by_id(
            args.repository_id,
            registry_path=args.registry,
            expected_config_digest=args.expected_config_digest,
        )
    except ValueError as exc:
        core.log(str(exc))
        return serial_worker.WORKER_CONFIG_CHANGED

    try:
        with serial_worker.repository_execution_lease(repository):
            processed = poll_repository_once(repository)
    except ExecutionLeaseBusy as exc:
        core.log(
            f"repository execution lease busy repository={repository.repository_id} "
            f"key={exc.key}"
        )
        return serial_worker.WORKER_BUSY
    except MachineResourceBusy as exc:
        core.log(
            f"machine resource busy repository={repository.repository_id} "
            f"resource={exc.resource}"
        )
        if exc.resource == "machine":
            return WORKER_MACHINE_BUSY
        return WORKER_RESOURCE_BUSY

    return serial_worker.WORKER_PROCESSED if processed else serial_worker.WORKER_IDLE


if __name__ == "__main__":
    raise SystemExit(main())
