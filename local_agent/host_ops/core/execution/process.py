"""Single owner for bounded local child-process lifecycle."""

from __future__ import annotations

import contextlib
import os
import re
import selectors
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import BinaryIO, cast

from .limits import ExecutionLimits
from .result import ProcessResult, ProcessState

_READ_CHUNK_BYTES = 64 * 1024
_POLL_INTERVAL_SECONDS = 0.05
_LOCAL_AGENT_LEASE_FDS_ENV = "LOCAL_AGENT_LEASE_FDS"
_LOCAL_AGENT_RESOURCE_LEASE_FDS_ENV = "LOCAL_AGENT_RESOURCE_LEASE_FDS"
_LOCAL_AGENT_LEASE_KEYS_DIGEST_ENV = "LOCAL_AGENT_LEASE_KEYS_DIGEST"
_LOCAL_AGENT_INTERNAL_ENV_NAMES = (
    _LOCAL_AGENT_LEASE_FDS_ENV,
    _LOCAL_AGENT_RESOURCE_LEASE_FDS_ENV,
    _LOCAL_AGENT_LEASE_KEYS_DIGEST_ENV,
)
_LEASE_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class _BoundedBuffer:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._buffer = bytearray()
        self.truncated = False

    @property
    def data(self) -> bytes:
        return bytes(self._buffer)

    def append(self, chunk: bytes) -> None:
        remaining = self._limit - len(self._buffer)
        if remaining > 0:
            self._buffer.extend(chunk[:remaining])
        if len(chunk) > max(remaining, 0):
            self.truncated = True

    def mark_incomplete(self) -> None:
        self.truncated = True


class DetachedProcessSpawner:
    """Spawn one persistent detached process through the shared execution boundary."""

    def spawn(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env_overrides: Mapping[str, str] | None = None,
    ) -> int:
        if os.name != "posix":
            raise RuntimeError("DetachedProcessSpawner currently requires a POSIX host")
        normalized_argv = _normalize_argv(argv)
        environment = _environment_with_overrides(env_overrides)
        _validate_local_agent_context(environment)
        child_environment = _child_environment(environment)
        try:
            process = subprocess.Popen(
                normalized_argv,
                cwd=cwd,
                env=child_environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"detached process spawn failed: {type(exc).__name__}: {exc}"
            ) from exc
        return int(process.pid)


class ProcessRunner:
    """Execute argv without a shell and return normalized bounded evidence."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env_overrides: Mapping[str, str] | None = None,
        limits: ExecutionLimits | None = None,
    ) -> ProcessResult:
        if os.name != "posix":
            raise RuntimeError("ProcessRunner currently requires a POSIX host")

        normalized_argv = _normalize_argv(argv)
        applied_limits = limits or ExecutionLimits()
        environment = _environment_with_overrides(env_overrides)
        nested_under_local_agent = _validate_local_agent_context(environment)
        child_environment = _child_environment(environment)
        started_at = time.monotonic()

        try:
            process = subprocess.Popen(
                normalized_argv,
                cwd=cwd,
                env=child_environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=not nested_under_local_agent,
            )
        except (OSError, ValueError) as exc:
            return ProcessResult(
                state=ProcessState.SPAWN_FAILED,
                exit_code=None,
                stdout="",
                stderr="",
                duration_seconds=time.monotonic() - started_at,
                error=f"{type(exc).__name__}: {exc}",
            )

        stdout = cast(BinaryIO, process.stdout)
        stderr = cast(BinaryIO, process.stderr)
        stdout_buffer = _BoundedBuffer(applied_limits.max_stdout_bytes)
        stderr_buffer = _BoundedBuffer(applied_limits.max_stderr_bytes)
        timed_out, lingering_descendants = _drain_process(
            process,
            stdout,
            stderr,
            stdout_buffer,
            stderr_buffer,
            applied_limits,
            started_at,
            owns_process_group=not nested_under_local_agent,
        )

        state = ProcessState.COMPLETED
        error: str | None = None
        if timed_out:
            state = ProcessState.TIMED_OUT
            error = f"process exceeded {applied_limits.timeout_seconds:g}s timeout"
        elif lingering_descendants:
            state = ProcessState.LINGERING_DESCENDANTS
            error = "process exited while local descendants were still alive"

        return ProcessResult(
            state=state,
            exit_code=process.returncode,
            stdout=stdout_buffer.data.decode("utf-8", errors="replace"),
            stderr=stderr_buffer.data.decode("utf-8", errors="replace"),
            duration_seconds=time.monotonic() - started_at,
            stdout_truncated=stdout_buffer.truncated,
            stderr_truncated=stderr_buffer.truncated,
            error=error,
        )


def _drain_process(
    process: subprocess.Popen[bytes],
    stdout: BinaryIO,
    stderr: BinaryIO,
    stdout_buffer: _BoundedBuffer,
    stderr_buffer: _BoundedBuffer,
    limits: ExecutionLimits,
    started_at: float,
    *,
    owns_process_group: bool,
) -> tuple[bool, bool]:
    selector = selectors.DefaultSelector()
    streams = {
        stdout.fileno(): (stdout, stdout_buffer),
        stderr.fileno(): (stderr, stderr_buffer),
    }
    for descriptor in streams:
        os.set_blocking(descriptor, False)
        selector.register(descriptor, selectors.EVENT_READ)

    timed_out = False
    lingering_descendants = False
    process_deadline = started_at + limits.timeout_seconds
    drain_deadline: float | None = None
    term_deadline: float | None = None
    kill_deadline: float | None = None

    try:
        while True:
            now = time.monotonic()
            process_alive = process.poll() is None

            if process_alive and not timed_out and now >= process_deadline:
                timed_out = True
                _signal_process_tree(process, signal.SIGTERM, owns_process_group)
                term_deadline = now + limits.terminate_grace_seconds

            process_alive = process.poll() is None
            if process_alive and timed_out and term_deadline is not None and now >= term_deadline:
                _signal_process_tree(process, signal.SIGKILL, owns_process_group)
                term_deadline = None

            process_alive = process.poll() is None
            if not process_alive and drain_deadline is None:
                drain_deadline = now + limits.pipe_drain_seconds

            group_alive = owns_process_group and _process_group_alive(process.pid)
            if (
                not process_alive
                and not lingering_descendants
                and drain_deadline is not None
                and now >= drain_deadline
                and (selector.get_map() or group_alive)
            ):
                lingering_descendants = True
                if owns_process_group:
                    _signal_process_group(process.pid, signal.SIGTERM)
                    term_deadline = now + limits.terminate_grace_seconds
                else:
                    _abandon_open_streams(selector, streams)
                    break

            group_alive = owns_process_group and _process_group_alive(process.pid)
            if (
                lingering_descendants
                and owns_process_group
                and term_deadline is not None
                and now >= term_deadline
            ):
                if group_alive:
                    _signal_process_group(process.pid, signal.SIGKILL)
                term_deadline = None
                kill_deadline = now + limits.terminate_grace_seconds

            group_alive = owns_process_group and _process_group_alive(process.pid)
            if (
                lingering_descendants
                and owns_process_group
                and kill_deadline is not None
                and now >= kill_deadline
                and (selector.get_map() or group_alive)
            ):
                _abandon_open_streams(selector, streams)
                break

            if not process_alive and not selector.get_map() and not group_alive:
                break

            if selector.get_map():
                events = selector.select(_POLL_INTERVAL_SECONDS)
                for key, _mask in events:
                    descriptor = key.fd
                    stream, buffer = streams[descriptor]
                    try:
                        chunk = os.read(descriptor, _READ_CHUNK_BYTES)
                    except BlockingIOError:
                        continue
                    if chunk:
                        buffer.append(chunk)
                        continue
                    selector.unregister(descriptor)
                    stream.close()
            else:
                time.sleep(_POLL_INTERVAL_SECONDS)

        if process.poll() is None:
            _signal_process_tree(process, signal.SIGKILL, owns_process_group)
        process.wait()
    finally:
        selector.close()
        stdout.close()
        stderr.close()

    return timed_out, lingering_descendants


def _normalize_argv(argv: Sequence[str]) -> tuple[str, ...]:
    if isinstance(argv, str | bytes):
        raise ValueError("argv must be a sequence of argument strings, not a single string")
    normalized = tuple(argv)
    if not normalized:
        raise ValueError("argv must contain at least one element")
    if not isinstance(normalized[0], str) or not normalized[0]:
        raise ValueError("argv[0] must be a non-empty string")
    if any(not isinstance(value, str) for value in normalized[1:]):
        raise ValueError("argv elements after argv[0] must be strings")
    if any("\x00" in value for value in normalized):
        raise ValueError("argv elements must not contain NUL bytes")
    return normalized


def _environment_with_overrides(overrides: Mapping[str, str] | None) -> dict[str, str]:
    environment = dict(os.environ)
    if overrides is None:
        return environment

    for name, value in overrides.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("environment override names and values must be strings")
        if not name or "=" in name or "\x00" in name:
            raise ValueError(
                "environment override names must be non-empty and contain no '=' or NUL"
            )
        if "\x00" in value:
            raise ValueError("environment override values must not contain NUL bytes")
        if name in _LOCAL_AGENT_INTERNAL_ENV_NAMES:
            raise ValueError(f"environment override may not change Local Agent lease state: {name}")
    environment.update(overrides)
    return environment


def _child_environment(environment: Mapping[str, str]) -> dict[str, str]:
    child = dict(environment)
    for name in _LOCAL_AGENT_INTERNAL_ENV_NAMES:
        child.pop(name, None)
    return child


def _validate_local_agent_context(environment: Mapping[str, str]) -> bool:
    repository_raw = environment.get(_LOCAL_AGENT_LEASE_FDS_ENV, "").strip()
    resource_raw = environment.get(_LOCAL_AGENT_RESOURCE_LEASE_FDS_ENV, "").strip()
    digest = environment.get(_LOCAL_AGENT_LEASE_KEYS_DIGEST_ENV, "").strip()

    if not repository_raw:
        if resource_raw or digest:
            raise ValueError("incomplete Local Agent lease state without repository lease")
        return False
    if not digest:
        raise ValueError("incomplete Local Agent lease state without repository lease digest")
    if not _LEASE_DIGEST_PATTERN.fullmatch(digest):
        raise ValueError(f"invalid {_LOCAL_AGENT_LEASE_KEYS_DIGEST_ENV}: {digest!r}")

    repository_fds = _parse_descriptors(_LOCAL_AGENT_LEASE_FDS_ENV, repository_raw)
    resource_fds = (
        _parse_descriptors(_LOCAL_AGENT_RESOURCE_LEASE_FDS_ENV, resource_raw)
        if resource_raw
        else ()
    )
    if set(repository_fds) & set(resource_fds):
        raise ValueError("Local Agent repository/resource lease descriptors overlap")

    descriptor_states = tuple(_descriptor_is_open(fd) for fd in (*repository_fds, *resource_fds))
    if any(descriptor_states) and not all(descriptor_states):
        raise ValueError("partially inherited Local Agent lease descriptors")
    return True


def _parse_descriptors(name: str, raw: str) -> tuple[int, ...]:
    parts = raw.split(",")
    try:
        descriptors = tuple(int(item) for item in parts)
    except ValueError:
        raise ValueError(f"invalid {name}: {raw!r}") from None
    if (
        not descriptors
        or any(fd < 3 for fd in descriptors)
        or len(set(descriptors)) != len(descriptors)
    ):
        raise ValueError(f"invalid {name}: {raw!r}")
    return descriptors


def _descriptor_is_open(descriptor: int) -> bool:
    try:
        os.fstat(descriptor)
    except OSError:
        return False
    return True


def _abandon_open_streams(
    selector: selectors.BaseSelector,
    streams: Mapping[int, tuple[BinaryIO, _BoundedBuffer]],
) -> None:
    for descriptor, (_stream, buffer) in streams.items():
        if descriptor not in selector.get_map():
            continue
        buffer.mark_incomplete()
        selector.unregister(descriptor)


def _process_group_alive(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _signal_process_tree(
    process: subprocess.Popen[bytes],
    sig: signal.Signals,
    owns_process_group: bool,
) -> None:
    if process.poll() is not None:
        return
    if owns_process_group:
        _signal_process_group(process.pid, sig)
        return
    with contextlib.suppress(ProcessLookupError):
        process.send_signal(sig)


def _signal_process_group(process_group_id: int, sig: signal.Signals) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process_group_id, sig)
