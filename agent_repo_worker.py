#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import agent_core as core
import agentd
from agent_repository import RepositoryContext, load_repository_registry

WORKER_IDLE = 0
WORKER_PROCESSED = 10


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


def poll_repository_once(repository: RepositoryContext) -> bool:
    """Poll one repository and execute at most one task."""
    bind_repository(repository)
    validate_repository_checkouts(repository)
    core.log(
        f"multi-repo poll repository={repository.repository_id} "
        f"remote={repository.repository}"
    )
    core.sync_control()
    agentd.recover_stale_claims()
    agentd.recover_invalid_task_files()
    pending = agentd.pending_tasks()
    if not pending:
        return False

    _, task = pending[0]
    core.log(
        f"multi-repo dispatch repository={repository.repository_id} "
        f"task={task.get('id')}"
    )
    agentd.execute_task(task)
    return True


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
