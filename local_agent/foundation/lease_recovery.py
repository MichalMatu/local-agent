"""Fail-closed recovery for orphaned repository execution-lease holders."""

from __future__ import annotations

import fcntl
import os
import shutil
import signal
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from local_agent.foundation.process import (
    LEASE_FDS_ENV,
    LEASE_KEYS_DIGEST_ENV,
    RESOURCE_LEASE_FDS_ENV,
    execution_lease_path,
    run_argv_bounded,
)
from local_agent.repository.context import RepositoryContext, repository_lease_keys

DEFAULT_TERMINATION_GRACE_SECONDS = 1.0
HOLDER_SCAN_TIMEOUT_SECONDS = 3.0
HOLDER_SCAN_OUTPUT_LIMIT = 16384


def repository_lease_paths(
    repositories: Iterable[RepositoryContext],
    *,
    state_dir: Path,
) -> tuple[Path, ...]:
    """Return every configured repository identity-lock path exactly once."""
    lock_dir = state_dir / "locks" / "repositories"
    paths = {
        execution_lease_path(lock_dir, key)
        for repository in repositories
        for key in repository_lease_keys(repository)
    }
    return tuple(sorted(paths))


def repository_leases_busy(paths: Iterable[Path]) -> bool:
    """Probe repository locks without rewriting their ownership metadata."""
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+", encoding="utf-8")
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
    return False


def _proc_holder_pids(paths: tuple[Path, ...]) -> set[int]:
    """Resolve actual FLOCK owners from Linux /proc/locks, not mere openers."""
    targets: set[tuple[int, int, int]] = set()
    for path in paths:
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        targets.add((os.major(stat.st_dev), os.minor(stat.st_dev), stat.st_ino))
    if not targets:
        return set()

    try:
        lines = Path("/proc/locks").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"cannot inspect Linux lock owners: {exc}") from exc

    holders: set[int] = set()
    for line in lines:
        fields = line.split()
        # Held locks have: id FLOCK ADVISORY WRITE pid major:minor:inode ...
        # Waiting locks contain an extra '->' token and are intentionally ignored.
        if len(fields) < 6 or fields[1] != "FLOCK":
            continue
        try:
            pid = int(fields[4])
            major_text, minor_text, inode_text = fields[5].split(":", 2)
            identity = (
                int(major_text, 16),
                int(minor_text, 16),
                int(inode_text, 10),
            )
        except (ValueError, TypeError):
            continue
        if identity in targets:
            holders.add(pid)
    return holders


def _lsof_holder_pids(
    paths: tuple[Path, ...],
    *,
    log: Callable[[str], None],
) -> set[int]:
    """Resolve actual lock owners using lsof's machine-readable lock field."""
    executable = shutil.which("lsof")
    if executable is None:
        raise RuntimeError("cannot inspect orphaned lease holders: lsof is unavailable")

    env = os.environ.copy()
    for name in (LEASE_FDS_ENV, LEASE_KEYS_DIGEST_ENV, RESOURCE_LEASE_FDS_ENV):
        env.pop(name, None)

    holders: set[int] = set()
    for path in paths:
        if not path.exists():
            continue
        result = run_argv_bounded(
            [executable, "-n", "-Fpl", "--", str(path)],
            cwd=path.parent,
            env=env,
            timeout=HOLDER_SCAN_TIMEOUT_SECONDS,
            output_limit=HOLDER_SCAN_OUTPUT_LIMIT,
            log=log,
        )
        exit_code = int(result.get("exit_code", 1))
        if exit_code not in (0, 1):
            raise RuntimeError(
                f"lease-holder inspection failed path={path} exit={exit_code}"
            )

        current_pid: int | None = None
        for line in str(result.get("output", "")).splitlines():
            if line.startswith("p") and line[1:].isdigit():
                current_pid = int(line[1:])
                continue
            # lsof field output uses `l<status>` for an applied file lock.
            # Any non-empty lock status is sufficient because repository leases
            # are the only locks intentionally placed on these identity files.
            if line.startswith("l") and line[1:] and current_pid is not None:
                holders.add(current_pid)
    return holders


def lease_holder_pids(
    paths: Iterable[Path],
    *,
    log: Callable[[str], None],
) -> set[int]:
    """Find processes that actually hold a lock on a configured repository lease."""
    resolved = tuple(dict.fromkeys(Path(path) for path in paths))
    if Path("/proc/locks").is_file():
        return _proc_holder_pids(resolved)
    return _lsof_holder_pids(resolved, log=log)


def _signal_process(pid: int, signum: int) -> None:
    try:
        os.kill(pid, signum)
    except ProcessLookupError:
        pass


def recover_orphaned_repository_leases(
    paths: Iterable[Path],
    *,
    log: Callable[[str], None],
    grace_seconds: float = DEFAULT_TERMINATION_GRACE_SECONDS,
) -> tuple[int, ...]:
    """Terminate stale lock holders after the supervisor and workers are stopped.

    This function is intentionally fail-closed. Callers must first stop the
    supervisor so every remaining holder is an orphaned command descendant.
    """
    resolved = tuple(dict.fromkeys(Path(path) for path in paths))
    if not resolved or not repository_leases_busy(resolved):
        return ()

    protected = {os.getpid(), os.getppid(), 0, 1}
    holders = lease_holder_pids(resolved, log=log)
    victims = tuple(sorted(pid for pid in holders if pid not in protected and pid > 1))
    if not victims:
        raise RuntimeError("repository lease is busy but no recoverable holder was found")

    log(f"recovering orphaned repository lease holders pids={list(victims)}")
    for pid in victims:
        _signal_process(pid, signal.SIGTERM)

    deadline = time.monotonic() + max(0.0, grace_seconds)
    remaining: set[int] = set(victims)
    while remaining and time.monotonic() < deadline:
        time.sleep(0.05)
        current = lease_holder_pids(resolved, log=log) - protected
        remaining.intersection_update(current)

    if remaining:
        log(f"killing orphaned repository lease holders pids={sorted(remaining)}")
        for pid in sorted(remaining):
            _signal_process(pid, signal.SIGKILL)

    verify_deadline = time.monotonic() + 1.0
    while time.monotonic() < verify_deadline:
        current = lease_holder_pids(resolved, log=log) - protected
        if not current and not repository_leases_busy(resolved):
            return victims
        time.sleep(0.05)

    current = lease_holder_pids(resolved, log=log) - protected
    if current:
        raise RuntimeError(
            f"orphaned repository lease holders survived recovery pids={sorted(current)}"
        )
    if repository_leases_busy(resolved):
        raise RuntimeError("repository lease remained busy after orphan recovery")
    return victims
