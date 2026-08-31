#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import agent_multirepo as serial
import agent_repo_worker as serial_worker
import agentd
from agent_parallel_worker import WORKER_RESOURCE_BUSY
from agent_process import (
    LEASE_FDS_ENV,
    LEASE_KEYS_DIGEST_ENV,
    ExecutionLeaseBusy,
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
)

MAX_WORKERS_ENV = "LOCAL_AGENT_MAX_PARALLEL_WORKERS"
DEFAULT_MAX_WORKERS = 1
MAX_MAX_WORKERS = 8
REAP_INTERVAL_SECONDS = 0.25
_daemon_lock_handle: Any | None = None


@dataclass
class RepositorySchedule:
    last_poll_at: float | None = None
    last_activity_at: float | None = None


@dataclass
class RunningWorker:
    repository_id: str
    proc: subprocess.Popen[str]
    started_at: float


def log(message: str) -> None:
    agentd.log(f"[parallel] {message}")


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


def reap_workers(
    running: dict[str, RunningWorker],
    schedules: dict[str, RepositorySchedule],
) -> None:
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
        schedule = schedules.setdefault(repository_id, RepositorySchedule())
        completed_at = time.monotonic()

        if return_code == serial_worker.WORKER_PROCESSED:
            schedule.last_activity_at = completed_at
            log(f"completed repository turn={repository_id}")
        elif return_code == WORKER_RESOURCE_BUSY:
            schedule.last_activity_at = completed_at
            log(f"resource wait deferred repository={repository_id}")
        elif return_code == serial_worker.WORKER_IDLE:
            pass
        elif return_code == serial_worker.WORKER_BUSY:
            log(f"repository turn deferred repository={repository_id}: lease busy")
        elif return_code == serial_worker.WORKER_CONFIG_CHANGED:
            log(f"repository turn deferred repository={repository_id}: config changed")
        else:
            log(
                f"repository worker failed repository={repository_id} "
                f"exit={return_code}"
            )


def repository_due(schedule: RepositorySchedule, now: float) -> bool:
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
        delays.append(serial.interval_remaining(schedule.last_poll_at, interval, now))
    return min(delays)


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


def service_control(
    repository: RepositoryContext,
    *,
    registry_path: Path | None,
    max_workers: int,
    once: bool,
) -> bool:
    try:
        with serial_worker.repository_execution_lease(repository):
            serial.bind_supervisor_control(repository)
            serial.sync_control_quietly()
            with route_parallel_restarts(
                registry_path=registry_path,
                max_workers=max_workers,
                once=once,
            ):
                agentd.handle_control_request()
                agentd.maybe_self_update()
        return True
    except ExecutionLeaseBusy:
        return False
    except Exception as exc:
        log(
            f"supervisor control degraded repository={repository.repository_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return False


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
        description="Experimental bounded parallel multi-repository local-agent supervisor."
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
    attempted_once: set[str] = set()

    repositories = load_repository_registry(path=args.registry)
    if not repositories:
        log("repository registry is empty")
        return 2

    control_repository = repositories[0]
    serial.bind_supervisor_control(control_repository)
    log(
        f"parallel supervisor starting max_workers={max_workers} "
        f"safe_fallback=agent_multirepo.py control_repository="
        f"{control_repository.repository_id}"
    )

    while True:
        now = time.monotonic()
        repositories = load_repository_registry(path=args.registry)
        schedules = {
            repository.repository_id: schedules.get(
                repository.repository_id,
                RepositorySchedule(),
            )
            for repository in repositories
        }

        reap_workers(running, schedules)

        if serial.interval_due(
            last_control_at,
            serial.SUPERVISOR_CONTROL_POLL_SECONDS,
            now,
        ):
            if repositories:
                control_repository = repositories[0]
                service_control(
                    control_repository,
                    registry_path=args.registry,
                    max_workers=max_workers,
                    once=args.once,
                )
            last_control_at = time.monotonic()

        capacity = max_workers - len(running)
        if capacity > 0:
            ordered = serial.ordered_repositories(repositories, last_repository)
            for repository in ordered:
                if capacity <= 0:
                    break
                if repository.repository_id in running:
                    continue
                schedule = schedules[repository.repository_id]
                if args.once:
                    if repository.repository_id in attempted_once:
                        continue
                elif not repository_due(schedule, now):
                    continue

                proc = start_worker(repository, registry_path=args.registry)
                schedule.last_poll_at = time.monotonic()
                if args.once:
                    attempted_once.add(repository.repository_id)
                if proc is None:
                    continue

                running[repository.repository_id] = RunningWorker(
                    repository_id=repository.repository_id,
                    proc=proc,
                    started_at=time.monotonic(),
                )
                last_repository = repository.repository_id
                capacity -= 1

        if args.once:
            enabled = {repository.repository_id for repository in repositories}
            if enabled.issubset(attempted_once) and not running:
                return 0

        now = time.monotonic()
        if running:
            delay = REAP_INTERVAL_SECONDS
        else:
            repository_delay = next_repository_delay(schedules, repositories, now)
            control_delay = serial.interval_remaining(
                last_control_at,
                serial.SUPERVISOR_CONTROL_POLL_SECONDS,
                now,
            )
            delay = min(repository_delay, control_delay, 1.0)
        time.sleep(max(0.05, delay))


if __name__ == "__main__":
    raise SystemExit(main())
