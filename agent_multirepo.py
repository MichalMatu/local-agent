#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import agent_storage as storage
import agentd
from agent_process import (
    ExecutionLeaseBusy,
    defer_termination_during_spawn,
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
from agent_repo_worker import (
    WORKER_BUSY,
    WORKER_CONFIG_CHANGED,
    WORKER_IDLE,
    WORKER_PROCESSED,
    repository_execution_lease,
)
from agent_version import RELEASE_VERSION

SUPERVISOR_VERSION = RELEASE_VERSION
POLL_SECONDS = 15.0
HOT_POLL_SECONDS = 2.0
WARM_POLL_SECONDS = 5.0
HOT_WINDOW_SECONDS = 30.0
WARM_WINDOW_SECONDS = 120.0
SUPERVISOR_CONTROL_POLL_SECONDS = POLL_SECONDS
WORKER_TURN_GRACE_SECONDS = 3600
_daemon_lock_handle: Any | None = None


def log(message: str) -> None:
    agentd.log(f"[multi-repo] {message}")


def sync_control_quietly() -> None:
    """Run bounded routine control-branch sync without printing low-level Git commands."""
    with contextlib.redirect_stdout(io.StringIO()):
        storage.sync_control(agentd.core)


def format_idle_summary(repository_count: int) -> str:
    noun = "repository" if repository_count == 1 else "repositories"
    return f"no pending task ({repository_count} {noun})"


def adaptive_poll_tier(
    last_activity_at: float | None,
    now: float,
) -> tuple[str, float]:
    """Return the polling tier for one repository from its latest task activity."""
    if last_activity_at is None:
        return "idle", POLL_SECONDS
    age = max(0.0, now - last_activity_at)
    if age < HOT_WINDOW_SECONDS:
        return "hot", HOT_POLL_SECONDS
    if age < WARM_WINDOW_SECONDS:
        return "warm", WARM_POLL_SECONDS
    return "idle", POLL_SECONDS


def interval_due(last_at: float | None, interval: float, now: float) -> bool:
    return last_at is None or now - last_at >= interval


def interval_remaining(last_at: float | None, interval: float, now: float) -> float:
    if last_at is None:
        return 0.0
    return max(0.0, interval - max(0.0, now - last_at))


def scheduler_sleep_seconds(
    *,
    active_repository: str | None,
    last_activity_at: float | None,
    last_active_poll_at: float | None,
    last_full_scan_at: float | None,
    last_control_service_at: float | None,
    now: float,
) -> float:
    """Wake for the earliest repository, full-scan or supervisor-control deadline."""
    if active_repository is not None:
        _, interval = adaptive_poll_tier(last_activity_at, now)
        return min(
            interval_remaining(last_active_poll_at, interval, now),
            interval_remaining(last_full_scan_at, POLL_SECONDS, now),
            interval_remaining(
                last_control_service_at,
                SUPERVISOR_CONTROL_POLL_SECONDS,
                now,
            ),
        )
    return min(
        interval_remaining(last_full_scan_at, POLL_SECONDS, now),
        interval_remaining(
            last_control_service_at,
            SUPERVISOR_CONTROL_POLL_SECONDS,
            now,
        ),
    )


def scheduler_due_actions(
    *,
    active_repository: str | None,
    last_activity_at: float | None,
    last_active_poll_at: float | None,
    last_full_scan_at: float | None,
    last_control_service_at: float | None,
    now: float,
) -> tuple[str, ...]:
    """Select due work with control and full-scan priority over hot polling."""
    actions: list[str] = []
    if interval_due(
        last_control_service_at,
        SUPERVISOR_CONTROL_POLL_SECONDS,
        now,
    ):
        actions.append("control")
    full_scan_due = interval_due(last_full_scan_at, POLL_SECONDS, now)
    if full_scan_due:
        actions.append("full_scan")
    elif active_repository is not None:
        _, active_interval = adaptive_poll_tier(last_activity_at, now)
        if interval_due(last_active_poll_at, active_interval, now):
            actions.append("active_poll")
    return tuple(actions)


def supervisor_control_repository(
    *,
    registry_path: Path | None,
) -> RepositoryContext:
    repositories = load_repository_registry(path=registry_path)
    return repositories[0]


def bind_supervisor_control(repository: RepositoryContext) -> None:
    agentd.core.CONTROL = repository.control
    agentd.core.CONTROL_BRANCH = repository.control_branch
    agentd.DAEMON_VERSION = SUPERVISOR_VERSION


def service_supervisor_control(
    repository: RepositoryContext,
    *,
    sync: bool = True,
) -> None:
    bind_supervisor_control(repository)
    if sync:
        sync_control_quietly()
    agentd.handle_control_request()
    agentd.maybe_self_update()


def service_supervisor_control_safely(
    repository: RepositoryContext,
    *,
    sync: bool = True,
) -> bool:
    try:
        with repository_execution_lease(repository):
            service_supervisor_control(repository, sync=sync)
    except ExecutionLeaseBusy:
        log(
            f"supervisor control deferred repository="
            f"{repository.repository_id}: execution lease busy"
        )
        return False
    except Exception as exc:
        log(
            f"supervisor control service degraded repository="
            f"{repository.repository_id}: {type(exc).__name__}: {exc}"
        )
        return False
    return True


def ordered_repositories(
    repositories: list[RepositoryContext],
    start_after: str | None,
) -> list[RepositoryContext]:
    if not repositories or start_after is None:
        return list(repositories)
    for index, repository in enumerate(repositories):
        if repository.repository_id == start_after:
            start = (index + 1) % len(repositories)
            return repositories[start:] + repositories[:start]
    return list(repositories)


def worker_command(
    repository: RepositoryContext,
    *,
    registry_path: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve().with_name("agent_repo_worker.py")),
        "--repository-id",
        repository.repository_id,
        "--expected-config-digest",
        repository_config_digest(repository),
    ]
    if registry_path is not None:
        command.extend(["--registry", str(registry_path)])
    return command


def run_worker(
    repository: RepositoryContext,
    *,
    registry_path: Path | None,
) -> int:
    try:
        with repository_execution_lease(repository):
            command = worker_command(repository, registry_path=registry_path)
            env = os.environ.copy()
            env["LOCAL_AGENT_SUPERVISOR_PID"] = str(os.getpid())
            proc = popen_registered(
                command,
                cwd=Path(__file__).resolve().parent,
                env=env,
                text=True,
                start_new_session=True,
            )
            setattr(proc, "_local_agent_process_group", proc.pid)
            try:
                try:
                    return proc.wait(
                        timeout=agentd.TIMEOUTS.task_max + WORKER_TURN_GRACE_SECONDS
                    )
                except subprocess.TimeoutExpired:
                    log(
                        f"repository worker timed out "
                        f"repository={repository.repository_id} "
                        f"limit={agentd.TIMEOUTS.task_max + WORKER_TURN_GRACE_SECONDS}s"
                    )
                    terminate_process_group(proc, log)
                    return 124
            finally:
                unregister_process(proc)
    except ExecutionLeaseBusy:
        return WORKER_BUSY


def shutdown_handler(signum: int, _frame: Any) -> None:
    if defer_termination_during_spawn(signum):
        return
    log(f"received signal {signum}; terminating active processes")
    terminate_active_processes(log)
    raise SystemExit(128 + signum)


def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)


def run_repository_cycle(
    repository_id: str,
    *,
    registry_path: Path | None,
) -> bool:
    """Poll exactly one active repository without waking idle repositories."""
    repositories = load_repository_registry(path=registry_path)
    matches = [item for item in repositories if item.repository_id == repository_id]
    if not matches:
        raise ValueError(f"repository id is not enabled: {repository_id!r}")
    repository = matches[0]
    return_code = run_worker(repository, registry_path=registry_path)
    if return_code == WORKER_PROCESSED:
        log(f"completed repository turn={repository.repository_id}")
        return True
    if return_code == WORKER_IDLE:
        return False
    if return_code == WORKER_BUSY:
        log(f"repository turn deferred repository={repository.repository_id}: lease busy")
        return False
    if return_code == WORKER_CONFIG_CHANGED:
        log(
            f"repository turn deferred repository={repository.repository_id}: "
            "configuration changed"
        )
        return False
    log(
        f"repository worker failed repository={repository.repository_id} "
        f"exit={return_code}; keeping scheduler alive"
    )
    return False


def run_cycle(
    *,
    registry_path: Path | None,
    start_after: str | None,
) -> tuple[bool, str | None]:
    repositories = load_repository_registry(path=registry_path)
    for repository in ordered_repositories(repositories, start_after):
        return_code = run_worker(repository, registry_path=registry_path)
        if return_code == WORKER_PROCESSED:
            log(f"completed repository turn={repository.repository_id}")
            return True, repository.repository_id
        if return_code == WORKER_IDLE:
            continue
        if return_code == WORKER_BUSY:
            log(f"repository turn deferred repository={repository.repository_id}: lease busy")
            continue
        if return_code == WORKER_CONFIG_CHANGED:
            log(
                f"repository turn deferred repository={repository.repository_id}: "
                "configuration changed"
            )
            continue
        log(
            f"repository worker failed repository={repository.repository_id} "
            f"exit={return_code}; continuing with other repositories"
        )
    return False, start_after


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Single-daemon multi-repository local-agent supervisor."
    )
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> int:
    global _daemon_lock_handle
    args = parse_args()
    _daemon_lock_handle = agentd.acquire_daemon_lock()
    install_signal_handlers()
    registry_path = args.registry
    last_repository: str | None = None
    active_repository: str | None = None
    last_activity_at: float | None = None
    last_active_poll_at: float | None = None
    last_full_scan_at: float | None = None
    last_control_service_at: float | None = None
    idle_announced = False
    control_repository = supervisor_control_repository(registry_path=registry_path)
    bind_supervisor_control(control_repository)
    log(
        f"supervisor {SUPERVISOR_VERSION} starting; "
        "global execution concurrency=1 "
        f"control_repository={control_repository.repository_id}; "
        f"adaptive_polling=hot:{HOT_POLL_SECONDS:g}s/{HOT_WINDOW_SECONDS:g}s "
        f"warm:{WARM_POLL_SECONDS:g}s/{WARM_WINDOW_SECONDS:g}s "
        f"idle:{POLL_SECONDS:g}s"
    )
    try:
        with repository_execution_lease(control_repository):
            sync_control_quietly()
            agentd.publish_daemon_status(
                "idle",
                force_remote=True,
                execution_model="multi_repository_supervisor",
                supervisor_pid=os.getpid(),
                supervisor_control_repository=control_repository.repository_id,
            )
    except ExecutionLeaseBusy:
        log(
            f"initial supervisor control service deferred repository="
            f"{control_repository.repository_id}: execution lease busy"
        )
    except Exception as exc:
        log(
            f"initial supervisor control service degraded: "
            f"{type(exc).__name__}: {exc}"
        )
    last_control_service_at = time.monotonic()

    while True:
        try:
            now = time.monotonic()
            if (
                active_repository is not None
                and last_activity_at is not None
                and now - last_activity_at >= WARM_WINDOW_SECONDS
            ):
                log(f"adaptive polling repository={active_repository} tier=idle")
                active_repository = None
                last_activity_at = None
                last_active_poll_at = None

            now = time.monotonic()
            due_actions = scheduler_due_actions(
                active_repository=active_repository,
                last_activity_at=last_activity_at,
                last_active_poll_at=last_active_poll_at,
                last_full_scan_at=last_full_scan_at,
                last_control_service_at=last_control_service_at,
                now=now,
            )
            if "control" in due_actions:
                control_repository = supervisor_control_repository(
                    registry_path=registry_path
                )
                service_supervisor_control_safely(control_repository)
                last_control_service_at = time.monotonic()

            if "full_scan" in due_actions:
                processed, scanned_repository = run_cycle(
                    registry_path=registry_path,
                    start_after=last_repository,
                )
                completed_at = time.monotonic()
                last_full_scan_at = completed_at
                if processed and scanned_repository is not None:
                    last_repository = scanned_repository
                    active_repository = scanned_repository
                    last_activity_at = completed_at
                    last_active_poll_at = completed_at
                    idle_announced = False
                    log(
                        f"adaptive polling repository={active_repository} "
                        f"tier=hot interval={HOT_POLL_SECONDS:g}s"
                    )
                elif not processed:
                    active_repository = None
                    last_activity_at = None
                    last_active_poll_at = None
            elif "active_poll" in due_actions:
                assert active_repository is not None
                processed = run_repository_cycle(
                    active_repository,
                    registry_path=registry_path,
                )
                completed_at = time.monotonic()
                last_active_poll_at = completed_at
                if processed:
                    last_repository = active_repository
                    last_activity_at = completed_at
                    idle_announced = False
                    log(
                        f"adaptive polling repository={active_repository} "
                        f"tier=hot interval={HOT_POLL_SECONDS:g}s"
                    )

        except Exception as exc:
            idle_announced = False
            log(f"registry/scheduler cycle failed: {type(exc).__name__}: {exc}")
            if args.once:
                return 2
            time.sleep(POLL_SECONDS)
            continue

        if args.once:
            return 0
        if active_repository is None and not idle_announced:
            repository_count = len(load_repository_registry(path=registry_path))
            log(format_idle_summary(repository_count))
            idle_announced = True

        now = time.monotonic()
        delay = scheduler_sleep_seconds(
            active_repository=active_repository,
            last_activity_at=last_activity_at,
            last_active_poll_at=last_active_poll_at,
            last_full_scan_at=last_full_scan_at,
            last_control_service_at=last_control_service_at,
            now=now,
        )
        time.sleep(max(0.05, delay))


if __name__ == "__main__":
    raise SystemExit(main())
