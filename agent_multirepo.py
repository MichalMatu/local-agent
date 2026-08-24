#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import agentd
from agent_process import terminate_process_group
from agent_repository import RepositoryContext, load_repository_registry
from agent_repo_worker import WORKER_IDLE, WORKER_PROCESSED

SUPERVISOR_VERSION = "4.6.0"
POLL_SECONDS = 15
_active_worker: subprocess.Popen[str] | None = None
_daemon_lock_handle: Any | None = None


def log(message: str) -> None:
    agentd.log(f"[multi-repo] {message}")


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


def service_supervisor_control(repository: RepositoryContext) -> None:
    bind_supervisor_control(repository)
    agentd.core.sync_control()
    agentd.handle_control_request()
    agentd.maybe_self_update()


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
    ]
    if registry_path is not None:
        command.extend(["--registry", str(registry_path)])
    return command


def run_worker(
    repository: RepositoryContext,
    *,
    registry_path: Path | None,
) -> int:
    global _active_worker
    command = worker_command(repository, registry_path=registry_path)
    log(f"polling repository={repository.repository_id}")
    env = os.environ.copy()
    env["LOCAL_AGENT_SUPERVISOR_PID"] = str(os.getpid())
    proc = subprocess.Popen(
        command,
        cwd=Path(__file__).resolve().parent,
        env=env,
        text=True,
        start_new_session=True,
    )
    setattr(proc, "_local_agent_process_group", proc.pid)
    _active_worker = proc
    try:
        return proc.wait()
    finally:
        _active_worker = None


def shutdown_handler(signum: int, _frame: Any) -> None:
    proc = _active_worker
    if proc is not None:
        log(f"received signal {signum}; terminating repository worker")
        terminate_process_group(proc, log)
    raise SystemExit(128 + signum)


def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)


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
        log(
            f"repository worker failed repository={repository.repository_id} "
            f"exit={return_code}; continuing with other repositories"
        )
    return False, start_after


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experimental v4.6 single-daemon multi-repository supervisor."
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
    control_repository = supervisor_control_repository(registry_path=registry_path)
    bind_supervisor_control(control_repository)
    log(
        f"supervisor {SUPERVISOR_VERSION} starting; "
        "global execution concurrency=1 "
        f"control_repository={control_repository.repository_id}"
    )
    agentd.core.sync_control()
    agentd.publish_daemon_status(
        "idle",
        force_remote=True,
        execution_model="multi_repository_supervisor",
        supervisor_pid=os.getpid(),
        supervisor_control_repository=control_repository.repository_id,
    )

    while True:
        try:
            control_repository = supervisor_control_repository(registry_path=registry_path)
            service_supervisor_control(control_repository)
            processed, last_repository = run_cycle(
                registry_path=registry_path,
                start_after=last_repository,
            )
        except Exception as exc:
            log(f"registry/scheduler cycle failed: {type(exc).__name__}: {exc}")
            if args.once:
                return 2
            time.sleep(POLL_SECONDS)
            continue
        if args.once:
            return 0
        if not processed:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
