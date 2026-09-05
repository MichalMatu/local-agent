#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path

import agent_core as core
import agent_operator
import agentd
import agent_repo_worker as serial_worker
from agent_binding import validate_repository_control_binding
from agent_process import ExecutionLeaseBusy
from agent_repository import RepositoryContext
from local_agent.runtime.task_contract import require_task_agent_binding
from local_agent.supervisor import resources as resource_admission

WORKER_RESOURCE_BUSY = 13
WORKER_MACHINE_BUSY = 14
PARALLEL_DAEMON_VERSION = serial_worker.MULTIREPO_DAEMON_VERSION
MachineResourceBusy = resource_admission.MachineResourceBusy


def resource_lock_dir() -> Path:
    return resource_admission.resource_lock_dir(agentd.STATE_DIR)


def task_resources(task: dict[str, object]) -> tuple[str, ...]:
    """Return the explicit validated external resource contract for one task."""
    return resource_admission.task_resources(task)


@contextlib.contextmanager
def machine_resource_lease(task: dict[str, object]) -> Iterator[tuple[str, ...]]:
    """Acquire external machine resources without waiting after task selection."""
    with resource_admission.machine_resource_lease(
        task,
        lock_dir=resource_lock_dir(),
        command_env=core.ENV,
    ) as resources:
        yield resources


def _waiting_status_context(task_id: str, resource: str) -> tuple[str, bool]:
    """Preserve the first wait timestamp and detect a materially changed wait."""
    try:
        payload = json.loads(agentd.LOCAL_STATUS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, AttributeError):
        payload = {}
    same_wait = (
        payload.get("state") == "waiting_resource"
        and payload.get("pending_task_id") == task_id
        and payload.get("blocked_resources") == [resource]
    )
    waiting_since = payload.get("waiting_since") if same_wait else None
    if not isinstance(waiting_since, str) or not waiting_since:
        waiting_since = agentd.now_iso()
    return waiting_since, not same_wait


def _reject_task_binding(repository: RepositoryContext, task: dict[str, object]) -> None:
    task_id = str(task.get("id", ""))
    expected = repository.agent_binding
    provided = task.get("agent_binding")
    failure_reason = "agent_binding_missing" if provided is None else "agent_binding_mismatch"
    result = {
        "id": task_id,
        "status": "failed",
        "failure_reason": failure_reason,
        "task_digest": agentd.task_digest(task),
        "started_at": None,
        "finished_at": agentd.now_iso(),
        "daemon_version": PARALLEL_DAEMON_VERSION,
        "repository_id": repository.repository_id,
        "repository": repository.repository,
        "expected_agent_binding": expected,
        "provided_agent_binding": provided,
        "error": "Task rejected before claim because its agent_binding does not match the bound repository.",
    }
    core.publish_result(task_id, result)
    agentd.publish_run_state(
        task_id,
        {
            "event": "task_rejected",
            "status": "failed",
            "failure_reason": failure_reason,
            "expected_agent_binding": expected,
            "provided_agent_binding": provided,
            "updated_at": agentd.now_iso(),
        },
        force_remote=True,
    )
    core.log(
        f"agent binding rejected repository={repository.repository_id} task={task_id} "
        f"expected={expected} provided={provided}"
    )


def _repository_binding_ready(repository: RepositoryContext) -> bool:
    if repository.agent_binding is None:
        serial_worker.publish_repository_status(
            repository,
            "unbound",
            force_remote=True,
            execution_variant="parallel",
            error="repository registry is missing agent_binding",
        )
        core.log(f"repository admission blocked: missing agent_binding repository={repository.repository_id}")
        return False
    try:
        validate_repository_control_binding(
            repository_id=repository.repository_id,
            repository=repository.repository,
            expected_agent_binding=repository.agent_binding,
            control_dir=repository.control,
        )
    except ValueError as exc:
        serial_worker.publish_repository_status(
            repository,
            "binding_error",
            force_remote=True,
            execution_variant="parallel",
            error=str(exc),
        )
        core.log(f"repository admission blocked by binding check repository={repository.repository_id}: {exc}")
        return False
    return True


def poll_repository_once(repository: RepositoryContext) -> bool:
    """Poll one repository and execute at most one resource-arbitrated task."""
    serial_worker.bind_repository(repository)
    serial_worker.validate_repository_checkouts(repository)
    previous_version = agentd.DAEMON_VERSION
    agentd.DAEMON_VERSION = PARALLEL_DAEMON_VERSION
    try:
        serial_worker.sync_control_quietly()
        if agent_operator.is_disabled():
            serial_worker.publish_repository_status(
                repository,
                "disabled",
                force_remote=True,
                execution_variant="parallel",
            )
            return False
        if not _repository_binding_ready(repository):
            return False
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
        task_id = str(task.get("id", ""))
        try:
            assert repository.agent_binding is not None
            require_task_agent_binding(task, repository.agent_binding)
        except ValueError:
            _reject_task_binding(repository, task)
            return True

        try:
            with machine_resource_lease(task) as resources:
                serial_worker.publish_repository_status(
                    repository,
                    "running",
                    force_remote=True,
                    current_task_id=task_id,
                    active_resources=list(resources),
                    execution_variant="parallel",
                )
                core.log(
                    f"[parallel] TASK START repository={repository.repository_id} "
                    f"task={task_id} binding={repository.agent_binding} resources={list(resources)}"
                )
                with serial_worker.ActiveRepositoryControlWatcher(repository, task_id):
                    outcome = agentd.execute_task(
                        task,
                        remote_daemon_status=False,
                        remote_result_published=False,
                    )
        except MachineResourceBusy as exc:
            waiting_since, force_remote = _waiting_status_context(task_id, exc.resource)
            serial_worker.publish_repository_status(
                repository,
                "waiting_resource",
                force_remote=force_remote,
                current_task_id=None,
                pending_task_id=task_id,
                blocked_resources=[exc.resource],
                waiting_since=waiting_since,
                retrying=True,
                execution_variant="parallel",
            )
            raise

        state = "publication_pending" if outcome == "publication_pending" else "idle"
        serial_worker.publish_repository_status(
            repository,
            state,
            force_remote=True,
            last_task_id=task_id,
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
