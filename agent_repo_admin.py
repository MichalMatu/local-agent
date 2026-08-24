#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Iterable

from agent_repository import RepositoryContext, load_repository_registry


def clone_url(repository: RepositoryContext) -> str:
    return f"https://github.com/{repository.repository}.git"


def normalize_remote_url(value: str) -> str:
    remote = value.strip()
    prefixes = (
        "https://github.com/",
        "http://github.com/",
        "ssh://git@github.com/",
        "git@github.com:",
    )
    for prefix in prefixes:
        if remote.startswith(prefix):
            remote = remote[len(prefix) :]
            break
    if remote.endswith(".git"):
        remote = remote[:-4]
    return remote.strip("/")


def run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def validate_checkout(path: Path, repository: RepositoryContext, label: str) -> None:
    if not (path / ".git").exists():
        raise RuntimeError(f"{label} checkout missing: {path}")
    remote = run_git(["remote", "get-url", "origin"], cwd=path, timeout=30)
    if remote.returncode != 0:
        raise RuntimeError(f"{label} checkout has no readable origin: {remote.stdout.strip()}")
    actual = normalize_remote_url(remote.stdout)
    if actual != repository.repository:
        raise RuntimeError(
            f"{label} checkout origin mismatch: expected {repository.repository}, got {actual}"
        )


def validate_repository(repository: RepositoryContext) -> None:
    validate_checkout(repository.control, repository, "control")
    validate_checkout(repository.work, repository, "work")
    if repository.control.resolve() == repository.work.resolve():
        raise RuntimeError("control and work checkouts must be different paths")


def _clone_if_missing(
    repository: RepositoryContext,
    *,
    path: Path,
    branch: str,
    single_branch: bool,
    label: str,
) -> bool:
    if path.exists():
        validate_checkout(path, repository, label)
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    command = ["clone", "--branch", branch]
    if single_branch:
        command.append("--single-branch")
    command.extend([clone_url(repository), str(path)])
    result = run_git(command, timeout=900)
    if result.returncode != 0:
        raise RuntimeError(f"{label} clone failed: {result.stdout.strip()}")
    validate_checkout(path, repository, label)
    return True


def provision_repository(repository: RepositoryContext) -> dict[str, bool]:
    """Explicitly create missing control/work clones without overwriting existing paths."""
    control_created = _clone_if_missing(
        repository,
        path=repository.control,
        branch=repository.control_branch,
        single_branch=True,
        label="control",
    )
    work_created = _clone_if_missing(
        repository,
        path=repository.work,
        branch=repository.default_branch,
        single_branch=False,
        label="work",
    )
    repository.checkpoints.mkdir(parents=True, exist_ok=True)
    validate_repository(repository)
    return {
        "control_created": control_created,
        "work_created": work_created,
    }


def select_repositories(
    repositories: Iterable[RepositoryContext],
    repository_id: str | None,
) -> list[RepositoryContext]:
    selected = list(repositories)
    if repository_id is None:
        return selected
    matches = [item for item in selected if item.repository_id == repository_id]
    if not matches:
        raise ValueError(f"repository id is not enabled: {repository_id!r}")
    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Administer local-agent repository workspaces.")
    parser.add_argument("--registry", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List enabled repositories.")
    list_parser.add_argument("--repository-id")

    validate_parser = subparsers.add_parser(
        "validate", help="Validate repository workspace checkout identity."
    )
    validate_parser.add_argument("--repository-id")

    provision_parser = subparsers.add_parser(
        "provision", help="Explicitly create missing repository workspaces."
    )
    provision_parser.add_argument("--repository-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repositories = load_repository_registry(path=args.registry)
    selected = select_repositories(repositories, getattr(args, "repository_id", None))

    if args.command == "list":
        for repository in selected:
            print(
                f"{repository.repository_id}\t{repository.repository}\t"
                f"control={repository.control}\twork={repository.work}"
            )
        return 0

    if args.command == "validate":
        failures = 0
        for repository in selected:
            try:
                validate_repository(repository)
            except Exception as exc:
                failures += 1
                print(f"FAIL {repository.repository_id}: {type(exc).__name__}: {exc}")
            else:
                print(f"OK {repository.repository_id}: {repository.repository}")
        return 1 if failures else 0

    if args.command == "provision":
        repository = selected[0]
        result = provision_repository(repository)
        print(
            f"OK {repository.repository_id}: "
            f"control_created={result['control_created']} "
            f"work_created={result['work_created']}"
        )
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
