"""Guarded Local Agent service entrypoint with repository-independent emergency stop."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import agentd
from agent_process import terminate_process_group
from agent_repo_admin import provision_repository
from agent_version import RELEASE_VERSION
from local_agent.operator import local as agent_operator
from local_agent.operator import remote as agent_remote_operator
from local_agent.repository.context import RepositoryContext, load_repository_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
LOOP_SECONDS = 0.5
DISABLED_STATUS_SECONDS = 5.0
_stop_requested = False


def log(message: str) -> None:
    agentd.log(f"[entrypoint] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded Local Agent launcher")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--max-workers", type=int, default=1)
    return parser.parse_args()


def _signal_handler(signum: int, _frame: object) -> None:
    global _stop_requested
    log(f"received signal {signum}; stopping guarded supervisor")
    _stop_requested = True


def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)


def _cleanup_generated_python_noise(repository: RepositoryContext) -> int:
    root = repository.control / ".agent" / "patches"
    if not root.exists():
        return 0
    removed = 0
    for directory in sorted(root.rglob("__pycache__"), reverse=True):
        if directory.is_dir():
            removed += sum(1 for item in directory.rglob("*") if item.is_file())
            shutil.rmtree(directory)
    for suffix in ("*.pyc", "*.pyo"):
        for path in root.rglob(suffix):
            if path.is_file():
                path.unlink()
                removed += 1
    return removed


def prepare_repositories(repositories: list[RepositoryContext]) -> None:
    """Repair only bounded generated noise and explicitly missing checkouts."""
    for repository in repositories:
        removed = _cleanup_generated_python_noise(repository)
        if removed:
            log(
                f"removed generated control bytecode repository={repository.repository_id} "
                f"files={removed}"
            )
        control_missing = not (repository.control / ".git").exists()
        work_missing = not (repository.work / ".git").exists()
        if control_missing or work_missing:
            log(
                f"provisioning missing repository checkout repository={repository.repository_id} "
                f"control_missing={control_missing} work_missing={work_missing}"
            )
            provision_repository(repository)


def supervisor_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "agent_parallel.py"),
    ]
    if args.registry is not None:
        command.extend(["--registry", str(args.registry)])
    command.extend(["--max-workers", str(args.max_workers)])
    return command


def start_supervisor(args: argparse.Namespace) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.Popen(
        supervisor_command(args),
        cwd=REPO_ROOT,
        env=env,
        text=True,
        start_new_session=True,
    )
    log(f"started parallel supervisor pid={proc.pid}")
    return proc


def stop_supervisor(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    terminate_process_group(proc, log)


def publish_guard_status(state: str, *, max_workers: int) -> None:
    payload = agentd.daemon_status_payload(
        state,
        execution_model="guarded_parallel_entrypoint",
        entrypoint_pid=os.getpid(),
        supervisor_pid=None,
        max_parallel_workers=max_workers,
        active_repository_ids=[],
    )
    agentd.atomic_write_json(agentd.LOCAL_STATUS_PATH, payload)


def _self_reexec_args(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(REPO_ROOT / "agent_entrypoint.py")]
    if args.registry is not None:
        command.extend(["--registry", str(args.registry)])
    command.extend(["--max-workers", str(args.max_workers)])
    return command


def main() -> int:
    args = parse_args()
    install_signal_handlers()
    initial_revision = agentd.self_revision()
    remote = agent_remote_operator.RemoteOperatorState()
    child: subprocess.Popen[str] | None = None
    last_disabled_status = 0.0

    log(
        f"guarded entrypoint {RELEASE_VERSION} starting max_workers={args.max_workers} "
        f"revision={initial_revision}"
    )

    while not _stop_requested:
        try:
            agent_remote_operator.poll_remote_operator(
                remote,
                self_repo=agentd.SELF_REPO,
            )
        except Exception as exc:
            log(f"remote operator poll degraded: {type(exc).__name__}: {exc}")

        current_revision = agentd.self_revision()
        if (
            initial_revision is not None
            and current_revision is not None
            and current_revision != initial_revision
        ):
            log(
                f"self revision changed {initial_revision} -> {current_revision}; "
                "re-executing guarded entrypoint"
            )
            stop_supervisor(child)
            os.execv(sys.executable, _self_reexec_args(args))

        if agent_operator.is_disabled():
            if child is not None:
                stop_supervisor(child)
                child = None
            now = time.monotonic()
            if now - last_disabled_status >= DISABLED_STATUS_SECONDS:
                publish_guard_status("disabled", max_workers=args.max_workers)
                last_disabled_status = now
            time.sleep(LOOP_SECONDS)
            continue

        if child is not None and child.poll() is not None:
            log(f"parallel supervisor exited code={child.returncode}; scheduling restart")
            child = None

        if child is None:
            try:
                repositories = load_repository_registry(path=args.registry)
                if not repositories:
                    raise RuntimeError("repository registry is empty")
                prepare_repositories(repositories)
                child = start_supervisor(args)
            except Exception as exc:
                log(f"guarded supervisor start deferred: {type(exc).__name__}: {exc}")
                time.sleep(2.0)
                continue

        time.sleep(LOOP_SECONDS)

    stop_supervisor(child)
    return 0
