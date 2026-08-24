#!/usr/bin/env python3
from __future__ import annotations

import os
import queue
import signal
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

OUTPUT_QUEUE_CAPACITY = 256
OUTPUT_READ_SIZE = 8192


class BoundedTextBuffer:
    """Retain only the newest text up to a strict character limit."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("buffer limit must be positive")
        self.limit = limit
        self._chunks: deque[str] = deque()
        self._chars = 0

    def append(self, text: str) -> None:
        if not text:
            return
        if len(text) >= self.limit:
            self._chunks.clear()
            self._chunks.append(text[-self.limit :])
            self._chars = self.limit
            return

        self._chunks.append(text)
        self._chars += len(text)
        overflow = self._chars - self.limit
        while overflow > 0 and self._chunks:
            first = self._chunks[0]
            if len(first) <= overflow:
                self._chunks.popleft()
                self._chars -= len(first)
                overflow = self._chars - self.limit
                continue
            self._chunks[0] = first[overflow:]
            self._chars -= overflow
            overflow = 0

    def text(self) -> str:
        return "".join(self._chunks)

    def __len__(self) -> int:
        return self._chars


@dataclass
class OutputPump:
    process: subprocess.Popen[str]
    queue: queue.Queue[str | None]
    stop_event: threading.Event
    thread: threading.Thread

    def stop(self, timeout: float = 1.0) -> None:
        self.stop_event.set()
        self.thread.join(timeout=timeout)
        if self.process.stdout is not None:
            try:
                self.process.stdout.close()
            except (OSError, ValueError):
                pass
        if self.thread.is_alive():
            self.thread.join(timeout=timeout)


def spawn_shell(
    command: str,
    *,
    cwd: Path,
    env: Mapping[str, str],
) -> subprocess.Popen[str]:
    """Start one shell command in its own process group."""
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    setattr(proc, "_local_agent_process_group", proc.pid)
    return proc


def start_output_pump(
    proc: subprocess.Popen[str],
    *,
    capacity: int = OUTPUT_QUEUE_CAPACITY,
    read_size: int = OUTPUT_READ_SIZE,
) -> OutputPump:
    """Read stdout with bounded handoff so producers cannot grow daemon memory."""
    if capacity < 1 or read_size < 1:
        raise ValueError("output pump bounds must be positive")

    lines: queue.Queue[str | None] = queue.Queue(maxsize=capacity)
    stop_event = threading.Event()

    def put(item: str | None) -> bool:
        while not stop_event.is_set():
            try:
                lines.put(item, timeout=0.25)
                return True
            except queue.Full:
                continue
        return False

    def reader() -> None:
        assert proc.stdout is not None
        try:
            while not stop_event.is_set():
                chunk = proc.stdout.readline(read_size)
                if chunk == "":
                    break
                if not put(chunk):
                    return
        except (OSError, ValueError):
            return
        finally:
            put(None)

    thread = threading.Thread(target=reader, daemon=True, name="local-agent-output")
    thread.start()
    return OutputPump(proc, lines, stop_event, thread)


def process_group_for(proc: subprocess.Popen[str]) -> int | None:
    stored = getattr(proc, "_local_agent_process_group", None)
    if isinstance(stored, int) and stored > 1:
        return stored
    if proc.poll() is not None:
        return None
    try:
        process_group = os.getpgid(proc.pid)
    except (OSError, ProcessLookupError):
        return None
    return process_group if process_group > 1 else None


def process_group_alive(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def terminate_process_group(
    proc: subprocess.Popen[str],
    log: Callable[[str], None],
    *,
    grace_seconds: float = 5.0,
) -> None:
    """Terminate the complete child process group, including surviving descendants."""
    process_group = process_group_for(proc)
    if process_group is None or process_group == os.getpgrp():
        return

    log(f"terminating process group pgid={process_group}")
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        return

    deadline = time.monotonic() + max(0.0, grace_seconds)
    while time.monotonic() < deadline:
        proc.poll()
        if not process_group_alive(process_group):
            return
        time.sleep(0.05)

    proc.poll()
    if not process_group_alive(process_group):
        return
    log(f"killing process group pgid={process_group}")
    try:
        os.killpg(process_group, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
