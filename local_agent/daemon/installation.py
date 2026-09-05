"""Serialize installed-source validation and guarded entrypoint reexecution."""

from __future__ import annotations

import contextlib
import fcntl
import json
from collections.abc import Iterator
from pathlib import Path

from local_agent.foundation.process import atomic_write_text, fsync_directory


def pending_path(state_dir: Path) -> Path:
    return state_dir / "installation-pending.json"


def installation_pending(state_dir: Path) -> bool:
    try:
        pending_path(state_dir).lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def begin_installation(state_dir: Path, original: str, candidate: str) -> None:
    atomic_write_text(
        pending_path(state_dir),
        json.dumps({"original_revision": original, "candidate_revision": candidate}) + "\n",
    )


def finish_installation(state_dir: Path) -> None:
    pending_path(state_dir).unlink(missing_ok=True)
    fsync_directory(state_dir)


def require_completed_installation(state_dir: Path) -> None:
    if installation_pending(state_dir):
        raise RuntimeError(
            f"unfinished self-update requires operator recovery: {pending_path(state_dir)}"
        )


@contextlib.contextmanager
def installation_transaction(state_dir: Path) -> Iterator[bool]:
    """Try the installation lock without delaying emergency control polling.

    The descriptor is deliberately close-on-exec: the validated replacement
    process must not inherit an installation transaction from its predecessor.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "installation.lock").open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
