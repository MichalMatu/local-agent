from __future__ import annotations

import fcntl
import threading
from collections.abc import Callable
from pathlib import Path
from typing import IO, Self

CONTROL_GIT_LOCK_FILENAME = "local-agent-workflow-control.lock"


class ReentrantControlGitLock:
    """Serialize one control checkout across threads and independent processes."""

    def __init__(self, control: Path) -> None:
        self.control = control.resolve(strict=False)
        self._thread_lock = threading.RLock()
        self._depth = 0
        self._handle: IO[str] | None = None

    def __enter__(self) -> Self:
        self._thread_lock.acquire()
        try:
            if self._depth == 0:
                git_dir = self.control / ".git"
                if not git_dir.is_dir():
                    raise RuntimeError(
                        f"control checkout is not a normal Git checkout: {self.control}"
                    )
                handle = (git_dir / CONTROL_GIT_LOCK_FILENAME).open(
                    "a+",
                    encoding="utf-8",
                )
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                except BaseException:
                    handle.close()
                    raise
                self._handle = handle
            self._depth += 1
            return self
        except BaseException:
            self._thread_lock.release()
            raise

    def __exit__(
        self,
        _exc_type: object,
        _exc: object,
        _tb: object,
    ) -> None:
        try:
            if self._depth < 1:
                raise RuntimeError("control Git lock exit without matching enter")
            self._depth -= 1
            if self._depth == 0:
                handle = self._handle
                self._handle = None
                if handle is None:
                    raise RuntimeError("control Git lock lost its file handle")
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()
        finally:
            self._thread_lock.release()


_registry_guard = threading.Lock()
_registry: dict[Path, ReentrantControlGitLock] = {}


def control_git_lock(control: Path) -> ReentrantControlGitLock:
    """Return the process-local reentrant lock for one canonical control checkout."""
    canonical = Path(control).resolve(strict=False)
    with _registry_guard:
        lock = _registry.get(canonical)
        if lock is None:
            lock = ReentrantControlGitLock(canonical)
            _registry[canonical] = lock
        return lock


class DynamicControlGitLock:
    """Resolve the active checkout on each outer acquisition.

    Legacy runtime code mutates ``core.CONTROL`` when a short-lived repository worker
    is bound. Nested users must keep the exact same underlying lock even if that global
    changes while an outer critical section is active.
    """

    def __init__(self, control_getter: Callable[[], Path]) -> None:
        self._control_getter = control_getter
        self._local = threading.local()

    def _stack(self) -> list[ReentrantControlGitLock]:
        stack = getattr(self._local, "stack", None)
        if stack is None:
            stack = []
            self._local.stack = stack
        return stack

    def __enter__(self) -> Self:
        stack = self._stack()
        lock = stack[-1] if stack else control_git_lock(self._control_getter())
        lock.__enter__()
        stack.append(lock)
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        stack = self._stack()
        if not stack:
            raise RuntimeError("dynamic control Git lock exit without matching enter")
        lock = stack.pop()
        try:
            lock.__exit__(exc_type, exc, tb)
        finally:
            if not stack:
                try:
                    del self._local.stack
                except AttributeError:
                    pass
