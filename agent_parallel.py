#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import agent_multirepo as serial
import agent_repo_worker as serial_worker
import agentd
from agent_parallel_worker import (
    PARALLEL_DAEMON_VERSION,
    WORKER_MACHINE_BUSY,
    WORKER_RESOURCE_BUSY,
)
from agent_process import (
    LEASE_FDS_ENV,
    LEASE_KEYS_DIGEST_ENV,
    ExecutionLeaseBusy,
    acquire_execution_leases,
    defer_termination,
    popen_registered,
    terminate_active_processes,
    terminate_process_group,
    unregister_process,
)
from agent_repository import (
    RepositoryContext,
    load_repository_registry,
    repository_config_digest,
    repository_lease_keys,
)

MAX_WORKERS_ENV = "LOCAL_AGENT_MAX_PARALLEL_WORKERS"
DEFAULT_MAX_WORKERS = 1
MAX_MAX_WORKERS = 3
REAP_INTERVAL_SECONDS = 0.25
RESOURCE_RETRY_SECONDS = 1.0
ERROR_RETRY_SECONDS = 1.0
MAX_ONCE_DEFERRALS = 120
OPERATOR_IDLE_HEARTBEAT_SECONDS = 300.0
PARALLEL_EXECUTION_MODEL = "parallel_repository_supervisor"
_daemon_lock_handle: Any | None = None


class ControlProbeResult(Enum):
    CLEAR = "clear"
    PENDING = "pending"
    DEFERRED = "deferred"


@dataclass
class RepositorySchedule:
    last_poll_at: float | None = None
    last_activity_at: float | None = None
    retry_not_before: float = 0.0


@dataclass
class RunningWorker:
    repository_id: str
    proc: subprocess.Popen[str]
    started_at: float


def log(message: str) -> None:
    agentd.log(f"[parallel] {message}")


def format_operator_idle_summary(repository_count: int, max_workers: int) -> str:
    noun = "repository" if repository_count == 1 else "repositories"
    return (
        f"IDLE no active task ({repository_count} {noun}); "
        f"max_workers={max_workers}"
    )


def operator_idle_log_due(last_idle_log_at: float | None, now: float) -> bool:
    return (
        last_idle_log_at is None
        or now - last_idle_log_at >= OPERATOR_IDLE_HEARTBEAT_SECONDS
    )


def resolve_max_workers(cli_value: int | None) -> int:
    raw: object = cli_value if cli_value is not None else os.environ.get(
        MAX_WORKERS_ENV,
        str(DEFAULT_MAX_WORKERS),
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"invalid {MAX_WORKERS_ENV}: {raw!r}") from None
    if value < 1 or value > MAX_MAX_WORKERS:
        raise ValueError(
            f"{MAX_WORKERS_ENV} must be 1..{MAX_MAX_WORKERS}, got {value}"
        )
    return value


def worker_command(
    repository: RepositoryContext,
    *,
    registry_path: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve().with_name("agent_parallel_worker.py")),
        "--repository-id",
        repository.repository_id,
        "--expected-config-digest",
        repository_config_digest(repository),
    ]
    if registry_path is not None:
        command.extend(["--registry", str(registry_path)])
    return command


def start_worker(
    repository: RepositoryContext,
    *,
    registry_path: Path | None,
) -> subprocess.Popen[str] | None:
    try:
        with serial_worker.repository_execution_lease(repository):
            env = os.environ.copy()
            env["LOCAL_AGENT_SUPERVISOR_PID"] = str(os.getpid())
            proc = popen_registered(
                worker_command(repository, registry_path=registry_path),
                cwd=Path(__file__).resolve().parent,
                env=env,
                text=True,
                start_new_session=True,
            )
            setattr(proc, "_local_agent_process_group", proc.pid)
            return proc
    except ExecutionLeaseBusy:
        return None
    except OSError as exc:
        log(
            f"repository worker spawn failed repository={repository.repository_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return None


def reap_workers(
    running: dict[str, RunningWorker],
    schedules: dict[str, RepositorySchedule],
) -> dict[str, int]:
    completed: dict[str, int] = {}
    now = time.monotonic()
    worker_limit = agentd.TIMEOUTS.task_max + serial.WORKER_TURN_GRACE_SECONDS
    for repository_id, slot in list(running.items()):
        return_code = slot.proc.poll()
        if return_code is None and now - slot.started_at > worker_limit:
            log(
                f"repository worker timed out repository={repository_id} "
                f"limit={worker_limit}s"
            )
            terminate_process_group(slot.proc, log)
            return_code = slot.proc.poll()
            if return_code is None:
                continue

        if return_code is None:
            continue

        unregister_process(slot.proc)
        del running[repository_id]
        completed[repository_id] = return_code
        schedule = schedules.setdefault(repository_id, RepositorySchedule())
        completed_at = time.monotonic()

        if return_code == serial_worker.WORKER_PROCESSED:
            schedule.last_activity_at = completed_at
            schedule.retry_not_before = 0.0
            log(f"TASK DONE repository={repository_id}")
        elif return_code == WORKER_MACHINE_BUSY:
            schedule.retry_not_before = completed_at + RESOURCE_RETRY_SECONDS
            log(f"machine exclusion deferred repository={repository_id}")
        elif return_code == WORKER_RESOURCE_BUSY:
            schedule.retry_not_before = completed_at + RESOURCE_RETRY_SECONDS
            log(f"named resource deferred repository={repository_id}")
        elif return_code == serial_worker.WORKER_IDLE:
            schedule.retry_not_before = 0.0
        elif return_code == serial_worker.WORKER_BUSY:
            schedule.retry_not_before = completed_at + RESOURCE_RETRY_SECONDS
            log(f"repository turn deferred repository={repository_id}: lease busy")
        elif return_code == serial_worker.WORKER_CONFIG_CHANGED:
            schedule.retry_not_before = completed_at + RESOURCE_RETRY_SECONDS
            log(f"repository turn deferred repository={repository_id}: config changed")
        else:
            schedule.retry_not_before = completed_at + RESOURCE_RETRY_SECONDS
            log(
                f"repository worker failed repository={repository_id} "
                f"exit={return_code}"
            )
    return completed


def record_once_deferral(
    counts: dict[str, int],
    failed: set[str],
    repository_id: str,
    *,
    limit: int = MAX_ONCE_DEFERRALS,
) -> int:
    """Count a one-shot deferral and make bounded failure terminal."""
    count = counts.get(repository_id, 0) + 1
    counts[repository_id] = count
    if count >= limit:
        failed.add(repository_id)
    return count


def repository_due(schedule: RepositorySchedule, now: float) -> bool:
    if now < schedule.retry_not_before:
        return False
    _, interval = serial.adaptive_poll_tier(schedule.last_activity_at, now)
    return serial.interval_due(schedule.last_poll_at, interval, now)


def next_repository_delay(
    schedules: dict[str, RepositorySchedule],
    repositories: list[RepositoryContext],
    now: float,
) -> float:
    if not repositories:
        return serial.POLL_SECONDS
    delays: list[float] = []
    for repository in repositories:
        schedule = schedules.setdefault(repository.repository_id, RepositorySchedule())
        _, interval = serial.adaptive_poll_tier(schedule.last_activity_at, now)
        poll_delay = serial.interval_remaining(schedule.last_poll_at, interval, now)
        retry_delay = max(0.0, schedule.retry_not_before - now)
        delays.append(max(poll_delay, retry_delay))
    return min(delays)


def _restore_env_value(target: dict[str, str], name: str, previous: str | None) -> None:
    if previous is None:
        target.pop(name, None)
    else:
        target[name] = previous


@contextlib.contextmanager
def supervisor_control_leases(
    repositories: list[RepositoryContext],
) -> Iterator[None]:
    """Hold every configured repository identity through global control work."""
    if not repositories:
        raise ValueError("supervisor control requires at least one repository")
    keys = tuple(
        key
        for repository in repositories
        for key in repository_lease_keys(repository)
    )
    leases = acquire_execution_leases(serial_worker.repository_lease_dir(), keys)
    updates = leases.environment()
    previous_os = {name: os.environ.get(name) for name in updates}
    previous_core = {name: agentd.core.ENV.get(name) for name in updates}
    os.environ.update(updates)
    agentd.core.ENV.update(updates)
    try:
        yield
    finally:
        for target, previous in (
            (os.environ, previous_os),
            (agentd.core.ENV, previous_core),
        ):
            for name, value in previous.items():
                _restore_env_value(target, name, value)
        leases.close()


def restart_parallel_supervisor(
    reason: str,
    *,
    registry_path: Path | None,
    max_workers: int,
    once: bool,
) -> None:
    agentd.publish_daemon_status("restarting", force_remote=True, reason=reason)
    log(f"restarting parallel supervisor: {reason}")
    for name in (LEASE_FDS_ENV, LEASE_KEYS_DIGEST_ENV):
        os.environ.pop(name, None)
        agentd.core.ENV.pop(name, None)

    command = [sys.executable, str(Path(__file__).resolve())]
    if registry_path is not None:
        command.extend(["--registry", str(registry_path)])
    command.extend(["--max-workers", str(max_workers)])
    if once:
        command.append("--once")
    try:
        os.execv(command[0], command)
    except OSError as exc:
        log(f"exec restart failed; asking launchd to restart: {exc}")
        raise SystemExit(75) from exc


@contextlib.contextmanager
def route_parallel_restarts(
    *,
    registry_path: Path | None,
    max_workers: int,
    once: bool,
) -> Iterator[None]:
    original_restart = agentd.restart_self

    def routed_restart(reason: str) -> None:
        restart_parallel_supervisor(
            reason,
            registry_path=registry_path,
            max_workers=max_workers,
            once=once,
        )

    agentd.restart_self = routed_restart
    try:
        yield
    finally:
        agentd.restart_self = original_restart


def pending_control_request_from_bound_checkout() -> ControlProbeResult:
    """Classify a control request after a successful control-checkout sync."""
    path = agentd.core.CONTROL / agentd.REMOTE_CONTROL_REQUEST
    if not path.exists():
        return ControlProbeResult.CLEAR
    try:
        request = json.loads(path.read_text(encoding="utf-8"))
        control_id = str(request["id"])
        str(request["action"])
    except Exception as exc:
        log(f"invalid daemon control request during probe: {type(exc).__name__}: {exc}")
        return ControlProbeResult.CLEAR
    if not control_id or len(control_id) > 120:
        return ControlProbeResult.CLEAR
    try:
        published = agentd.control_ack_published(control_id)
    except Exception as exc:
        log(f"control ACK probe degraded id={control_id}: {type(exc).__name__}: {exc}")
        return ControlProbeResult.DEFERRED
    return ControlProbeResult.CLEAR if published else ControlProbeResult.PENDING


def probe_control_request(
    repository: RepositoryContext,
) -> ControlProbeResult:
    """Probe control while other repositories run without invoking global actions."""
    try:
        with serial_worker.repository_execution_lease(repository):
            serial.bind_supervisor_control(repository)
            serial.sync_control_quietly()
            return pending_control_request_from_bound_checkout()
    except ExecutionLeaseBusy:
        return ControlProbeResult.DEFERRED
    except Exception as exc:
        log(
            f"supervisor control probe degraded repository={repository.repository_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return ControlProbeResult.DEFERRED


def service_control(
    repositories: list[RepositoryContext],
    *,
    registry_path: Path | None,
    max_workers: int,
    once: bool,
) -> bool:
    if not repositories:
        return False
    control_repository = repositories[0]
    try:
        with supervisor_control_leases(repositories):
            serial.bind_supervisor_control(control_repository)
            agentd.DAEMON_VERSION = PARALLEL_DAEMON_VERSION
            serial.sync_control_quietly()
            agentd.publish_daemon_status(
                "idle",
                force_remote=False,
                execution_model=PARALLEL_EXECUTION_MODEL,
                supervisor_pid=os.getpid(),
                max_parallel_workers=max_workers,
                supervisor_control_repository=control_repository.repository_id,
            )
            with route_parallel_restarts(
                registry_path=registry_path,
                max_workers=max_workers,
                once=once,
            ):
                agentd.handle_control_request()
                agentd.maybe_self_update()
            agentd.publish_daemon_status(
                "idle",
                force_remote=False,
                execution_model=PARALLEL_EXECUTION_MODEL,
                supervisor_pid=os.getpid(),
                max_parallel_workers=max_workers,
                supervisor_control_repository=control_repository.repository_id,
            )
        return True
    except ExecutionLeaseBusy as exc:
        log(f"supervisor control deferred: repository lease busy key={exc.key}")
        return False
    except Exception as exc:
        log(
            f"supervisor control degraded repository={control_repository.repository_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return False


def publish_local_supervisor_status(
    running: dict[str, RunningWorker],
    *,
    max_workers: int,
) -> None:
    state = "running" if running else "idle"
    payload = agentd.daemon_status_payload(
        state,
        execution_model=PARALLEL_EXECUTION_MODEL,
        supervisor_pid=os.getpid(),
        max_parallel_workers=max_workers,
        active_repository_ids=sorted(running),
    )
    agentd.atomic_write_json(agentd.LOCAL_STATUS_PATH, payload)


def shutdown_handler(signum: int, _frame: Any) -> None:
    if defer_termination(signum):
        return
    log(f"received signal {signum}; terminating active processes")
    terminate_active_processes(log)
    raise SystemExit(128 + signum)


def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bounded parallel multi-repository local-agent supervisor."
    )
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--max-workers", type=int)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> int:
    global _daemon_lock_handle
    args = parse_args()
    try:
        max_workers = resolve_max_workers(args.max_workers)
    except ValueError as exc:
        log(str(exc))
        return 2

    _daemon_lock_handle = agentd.acquire_daemon_lock()
    install_signal_handlers()

    running: dict[str, RunningWorker] = {}
    schedules: dict[str, RepositorySchedule] = {}
    last_repository: str | None = None
    last_control_at: float | None = None
    control_pending = True
    priority_repository: str | None = None
    once_completed: set[str] = set()
    once_failed: set[str] = set()
    once_deferrals: dict[str, int] = {}
    last_idle_log_at: float | None = None

    try:
        repositories = load_repository_registry(path=args.registry)
    except Exception as exc:
        log(f"initial repository registry load failed: {type(exc).__name__}: {exc}")
        return 2
    if not repositories:
        log("repository registry is empty")
        return 2

    log(
        f"parallel supervisor {PARALLEL_DAEMON_VERSION} starting "
        f"max_workers={max_workers} safe_fallback=agent_multirepo.py "
        f"control_repository={repositories[0].repository_id}"
    )

    def note_once_deferral(repository_id: str) -> None:
        if not args.once:
            return
        count = record_once_deferral(
            once_deferrals,
            once_failed,
            repository_id,
        )
        if count >= MAX_ONCE_DEFERRALS:
            log(
                f"one-shot deferral limit exceeded repository={repository_id} "
                f"attempts={count}"
            )

    def record_once_outcomes(completed: dict[str, int]) -> None:
        if not args.once:
            return
        deferrable = {
            WORKER_MACHINE_BUSY,
            WORKER_RESOURCE_BUSY,
            serial_worker.WORKER_BUSY,
            serial_worker.WORKER_CONFIG_CHANGED,
        }
        for repository_id, return_code in completed.items():
            if return_code in {
                serial_worker.WORKER_PROCESSED,
                serial_worker.WORKER_IDLE,
            }:
                once_completed.add(repository_id)
                once_deferrals.pop(repository_id, None)
                continue
            if return_code in deferrable:
                note_once_deferral(repository_id)
                continue
            once_failed.add(repository_id)

    while True:
        try:
            completed = reap_workers(running, schedules)
            record_once_outcomes(completed)
            if any(
                return_code == serial_worker.WORKER_PROCESSED
                for return_code in completed.values()
            ):
                last_idle_log_at = None
            if completed:
                publish_local_supervisor_status(running, max_workers=max_workers)

            repositories = load_repository_registry(path=args.registry)
            if not repositories:
                if args.once and not running:
                    return 2
                time.sleep(ERROR_RETRY_SECONDS)
                continue

            schedules = {
                repository.repository_id: schedules.get(
                    repository.repository_id,
                    RepositorySchedule(),
                )
                for repository in repositories
            }
            enabled = {repository.repository_id for repository in repositories}
            once_completed.intersection_update(enabled)
            once_failed.intersection_update(enabled)
            once_deferrals = {
                repository_id: count
                for repository_id, count in once_deferrals.items()
                if repository_id in enabled
            }

            if priority_repository not in enabled:
                priority_repository = None

            for repository_id, return_code in completed.items():
                if (
                    priority_repository == repository_id
                    and return_code != WORKER_MACHINE_BUSY
                ):
                    priority_repository = None
                if (
                    return_code == WORKER_MACHINE_BUSY
                    and priority_repository is None
                    and repository_id in enabled
                    and repository_id not in once_failed
                ):
                    priority_repository = repository_id

            if args.once and priority_repository in once_failed:
                priority_repository = None

            if control_pending:
                if running:
                    time.sleep(REAP_INTERVAL_SECONDS)
                    continue
                if service_control(
                    repositories,
                    registry_path=args.registry,
                    max_workers=max_workers,
                    once=args.once,
                ):
                    last_control_at = time.monotonic()
                    control_pending = False
                else:
                    time.sleep(ERROR_RETRY_SECONDS)
                    continue

            now = time.monotonic()
            if serial.interval_due(
                last_control_at,
                serial.SUPERVISOR_CONTROL_POLL_SECONDS,
                now,
            ):
                if running:
                    probe_result = probe_control_request(repositories[0])
                    if probe_result is ControlProbeResult.PENDING:
                        control_pending = True
                        log("global control request detected; draining active workers")
                        time.sleep(REAP_INTERVAL_SECONDS)
                        continue
                    if probe_result is ControlProbeResult.DEFERRED:
                        time.sleep(ERROR_RETRY_SECONDS)
                        continue
                    last_control_at = time.monotonic()
                else:
                    if service_control(
                        repositories,
                        registry_path=args.registry,
                        max_workers=max_workers,
                        once=args.once,
                    ):
                        last_control_at = time.monotonic()
                    else:
                        time.sleep(ERROR_RETRY_SECONDS)
                        continue

            started_worker = False
            now = time.monotonic()

            if priority_repository is not None:
                if priority_repository not in running and not running:
                    repository = next(
                        item
                        for item in repositories
                        if item.repository_id == priority_repository
                    )
                    schedule = schedules[priority_repository]
                    if now >= schedule.retry_not_before:
                        proc = start_worker(repository, registry_path=args.registry)
                        schedule.last_poll_at = time.monotonic()
                        if proc is not None:
                            running[priority_repository] = RunningWorker(
                                repository_id=priority_repository,
                                proc=proc,
                                started_at=time.monotonic(),
                            )
                            last_repository = priority_repository
                            started_worker = True
                        else:
                            schedule.retry_not_before = (
                                time.monotonic() + RESOURCE_RETRY_SECONDS
                            )
                            note_once_deferral(priority_repository)
                            if args.once and priority_repository in once_failed:
                                priority_repository = None
            else:
                capacity = max_workers - len(running)
                if capacity > 0:
                    ordered = serial.ordered_repositories(
                        repositories,
                        last_repository,
                    )
                    for repository in ordered:
                        if capacity <= 0:
                            break
                        if repository.repository_id in running:
                            continue
                        if args.once and repository.repository_id in (
                            once_completed | once_failed
                        ):
                            continue
                        schedule = schedules[repository.repository_id]
                        if not args.once and not repository_due(schedule, now):
                            continue
                        if args.once and now < schedule.retry_not_before:
                            continue

                        proc = start_worker(repository, registry_path=args.registry)
                        schedule.last_poll_at = time.monotonic()
                        if proc is None:
                            schedule.retry_not_before = (
                                time.monotonic() + RESOURCE_RETRY_SECONDS
                            )
                            note_once_deferral(repository.repository_id)
                            continue

                        running[repository.repository_id] = RunningWorker(
                            repository_id=repository.repository_id,
                            proc=proc,
                            started_at=time.monotonic(),
                        )
                        last_repository = repository.repository_id
                        capacity -= 1
                        started_worker = True

            if started_worker:
                publish_local_supervisor_status(running, max_workers=max_workers)

            if args.once:
                terminal = once_completed | once_failed
                if enabled.issubset(terminal) and not running:
                    return 2 if once_failed else 0

            now = time.monotonic()
            if (
                not running
                and not control_pending
                and priority_repository is None
                and operator_idle_log_due(last_idle_log_at, now)
            ):
                log(format_operator_idle_summary(len(repositories), max_workers))
                last_idle_log_at = now

            if running or control_pending:
                delay = REAP_INTERVAL_SECONDS
            elif priority_repository is not None:
                retry_at = schedules[priority_repository].retry_not_before
                delay = max(0.05, min(RESOURCE_RETRY_SECONDS, retry_at - now))
            else:
                repository_delay = next_repository_delay(
                    schedules,
                    repositories,
                    now,
                )
                control_delay = serial.interval_remaining(
                    last_control_at,
                    serial.SUPERVISOR_CONTROL_POLL_SECONDS,
                    now,
                )
                delay = min(repository_delay, control_delay, 1.0)
            time.sleep(max(0.05, delay))
        except SystemExit:
            raise
        except Exception as exc:
            log(f"scheduler cycle failed: {type(exc).__name__}: {exc}")
            if args.once:
                return 2
            time.sleep(ERROR_RETRY_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
