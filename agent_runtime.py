#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import threading
import time
from typing import Any, Callable

ProgressCallback = Callable[[dict[str, Any]], None]

_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
DEFAULT_IDLE_TIMEOUT = 600
MAX_IDLE_TIMEOUT = 3600
DEFAULT_TASK_TIMEOUT = 3600
MAX_TASK_TIMEOUT = 14400
PROGRESS_INTERVAL = 30
MAX_OUTPUT = 60000
LIVE_DIFF_MAX_LINES = 80
LIVE_DIFF_MAX_CHARS = 12_000

_DIFF_METADATA_PREFIXES = (
    "index ",
    "--- ",
    "+++ ",
    "new file mode ",
    "deleted file mode ",
    "old mode ",
    "new mode ",
    "similarity index ",
    "dissimilarity index ",
    "rename from ",
    "rename to ",
    "copy from ",
    "copy to ",
    "Binary files ",
    "GIT binary patch",
    "literal ",
    "delta ",
    "\\ No newline at end of file",
)

_DIFF_HUNK_RE = re.compile(
    r"^@@ -\d+(?:,(?P<old_count>\d+))? "
    r"\+\d+(?:,(?P<new_count>\d+))? @@(?:.*)$"
)


class LiveCommandOutput:
    """Keep normal live output readable while retaining raw command output separately."""

    def __init__(self) -> None:
        self._in_diff = False
        self._in_hunk = False
        self._old_remaining = 0
        self._new_remaining = 0
        self._collapsed = False
        self._buffer: list[str] = []
        self._files = 0
        self._lines = 0
        self._chars = 0
        self._fingerprint = hashlib.sha256()
        self._last_collapsed_fingerprint: str | None = None
        self._repeated_collapsed_count = 0

    @staticmethod
    def _print_line(line: str) -> None:
        print(f"[CMD] {line}", end="", flush=True)

    def _reset_diff(self) -> None:
        self._in_diff = False
        self._in_hunk = False
        self._old_remaining = 0
        self._new_remaining = 0
        self._collapsed = False
        self._buffer.clear()
        self._files = 0
        self._lines = 0
        self._chars = 0
        self._fingerprint = hashlib.sha256()

    @staticmethod
    def _parse_hunk_header(line: str) -> tuple[int, int] | None:
        match = _DIFF_HUNK_RE.match(line.rstrip("\r\n"))
        if match is None:
            return None
        old_count = int(match.group("old_count") or "1")
        new_count = int(match.group("new_count") or "1")
        return old_count, new_count

    @staticmethod
    def _is_diff_metadata_line(line: str) -> bool:
        return line.rstrip("\r\n").startswith(_DIFF_METADATA_PREFIXES)

    def _consume_hunk_line(self, line: str) -> bool:
        if not self._in_hunk:
            return False
        text = line.rstrip("\r\n")
        if text.startswith(" "):
            self._old_remaining -= 1
            self._new_remaining -= 1
        elif text.startswith("-"):
            self._old_remaining -= 1
        elif text.startswith("+"):
            self._new_remaining -= 1
        else:
            return False
        self._record_diff_line(line)
        if self._old_remaining <= 0 and self._new_remaining <= 0:
            self._in_hunk = False
        return True

    def _record_diff_line(self, line: str) -> None:
        if line.startswith("diff --git "):
            self._files += 1
        self._lines += 1
        self._chars += len(line)
        self._fingerprint.update(line.encode("utf-8"))
        if not self._collapsed:
            self._buffer.append(line)
            if self._lines > LIVE_DIFF_MAX_LINES or self._chars > LIVE_DIFF_MAX_CHARS:
                self._collapsed = True
                self._buffer.clear()

    def _flush_repeated_notice(self) -> None:
        if self._repeated_collapsed_count == 0:
            return
        count = self._repeated_collapsed_count
        copies = "copy" if count == 1 else "copies"
        print(
            f"[CMD] [suppressed {count} repeated {copies} of the previous unified diff]",
            flush=True,
        )
        self._last_collapsed_fingerprint = None
        self._repeated_collapsed_count = 0

    def _emit_collapsed_diff(self) -> None:
        fingerprint = self._fingerprint.hexdigest()
        if fingerprint == self._last_collapsed_fingerprint:
            self._repeated_collapsed_count += 1
            return
        self._flush_repeated_notice()
        print(
            "[CMD] [large unified diff collapsed in live log; "
            "raw output remains in bounded task result buffer]",
            flush=True,
        )
        kib = self._chars / 1024.0
        print(
            f"[CMD] [collapsed unified diff: {self._files} file(s), "
            f"{self._lines} line(s), {kib:.1f} KiB]",
            flush=True,
        )
        self._last_collapsed_fingerprint = fingerprint

    def _flush_diff(self) -> None:
        if not self._in_diff:
            return
        if self._collapsed:
            self._emit_collapsed_diff()
        else:
            self._flush_repeated_notice()
            for line in self._buffer:
                self._print_line(line)
            self._last_collapsed_fingerprint = None
        self._reset_diff()

    def _emit_normal_line(self, line: str) -> None:
        if line.rstrip("\r\n"):
            self._flush_repeated_notice()
            self._last_collapsed_fingerprint = None
        self._print_line(line)

    def emit(self, line: str) -> None:
        if not self._in_diff:
            if line.startswith("diff --git "):
                self._in_diff = True
                self._record_diff_line(line)
                return
            self._emit_normal_line(line)
            return

        if line.startswith("diff --git "):
            self._in_hunk = False
            self._record_diff_line(line)
            return

        hunk_counts = self._parse_hunk_header(line)
        if hunk_counts is not None:
            self._old_remaining, self._new_remaining = hunk_counts
            self._in_hunk = self._old_remaining > 0 or self._new_remaining > 0
            self._record_diff_line(line)
            return

        if self._consume_hunk_line(line):
            return

        if self._is_diff_metadata_line(line):
            self._record_diff_line(line)
            return

        self._flush_diff()
        self._emit_normal_line(line)

    def finish(self) -> None:
        self._flush_diff()
        self._flush_repeated_notice()


def task_digest(task: dict[str, Any]) -> str:
    payload = json.dumps(
        task,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_task(task: dict[str, Any]) -> None:
    if not isinstance(task, dict):
        raise ValueError("task must be an object")
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id or len(task_id) > 200:
        raise ValueError("task id must be a non-empty string up to 200 characters")
    if not _TASK_ID_RE.fullmatch(task_id):
        raise ValueError("task id contains unsupported characters")
    if str(task.get("mode", "commands")) != "commands":
        raise ValueError("only mode=commands is supported")
    for field in ("writes", "deletes", "commands", "verify_commands"):
        if field in task and not isinstance(task[field], list):
            raise ValueError(f"{field} must be a list")


def _bounded_int(
    task: dict[str, Any],
    field: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw = task.get(field, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"invalid {field}: {raw!r}") from None
    if value < minimum or value > maximum:
        raise ValueError(f"{field} must be {minimum}..{maximum}, got {value}")
    return value


def idle_timeout_for(task: dict[str, Any]) -> int:
    return _bounded_int(task, "idle_timeout", DEFAULT_IDLE_TIMEOUT, 0, MAX_IDLE_TIMEOUT)


def task_timeout_for(task: dict[str, Any]) -> int:
    return _bounded_int(task, "task_timeout", DEFAULT_TASK_TIMEOUT, 1, MAX_TASK_TIMEOUT)


class RuntimeExecutor:
    def __init__(self, core_module: Any):
        self.core = core_module
        self._active_process: subprocess.Popen[str] | None = None
        self._active_lock = threading.Lock()
        self._progress: ProgressCallback | None = None
        self._deadline: float | None = None
        self._idle_timeout = DEFAULT_IDLE_TIMEOUT
        self._command_index = 0
        self._command_count = 0
        self._primary_count = 0
        self._last_failure_reason: str | None = None

    def _emit(self, event: dict[str, Any]) -> None:
        if self._progress is None:
            return
        try:
            self._progress(event)
        except Exception as exc:
            self.core.log(f"progress callback failed: {type(exc).__name__}: {exc}")

    def terminate_active_command(self) -> bool:
        with self._active_lock:
            proc = self._active_process
        if proc is None or proc.poll() is not None:
            return False
        self.core.kill_process_group(proc)
        return True

    def _phase(self) -> str:
        return "commands" if self._command_index <= self._primary_count else "verification"

    def run_command(self, command: str, timeout: int) -> dict[str, Any]:
        self._command_index += 1
        phase = self._phase()
        started = time.monotonic()
        last_output = started
        last_progress = started
        timed_out = False
        idle_timed_out = False
        task_timed_out = False

        self.core.log(f"exec: {command}")
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=self.core.WORK,
            env=self.core.ENV,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        with self._active_lock:
            self._active_process = proc

        self._emit(
            {
                "event": "command_started",
                "phase": phase,
                "index": self._command_index,
                "total": self._command_count,
                "command": command,
                "pid": proc.pid,
                "timeout": timeout,
                "idle_timeout": self._idle_timeout,
                "started_at": self.core.now_iso(),
            }
        )

        lines: queue.Queue[str | None] = queue.Queue()

        def reader() -> None:
            assert proc.stdout is not None
            try:
                for line in iter(proc.stdout.readline, ""):
                    lines.put(line)
            finally:
                lines.put(None)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        chunks: list[str] = []
        total_chars = 0
        reader_done = False
        live_output = LiveCommandOutput()

        try:
            while True:
                now = time.monotonic()
                elapsed = now - started
                if proc.poll() is None:
                    if self._deadline is not None and now >= self._deadline:
                        task_timed_out = True
                        self._last_failure_reason = "task_timeout"
                        self.core.log(f"TASK TIMEOUT while running: {command}")
                        self.core.kill_process_group(proc)
                    elif elapsed >= timeout:
                        timed_out = True
                        self._last_failure_reason = (
                            "verification_timeout" if phase == "verification" else "command_timeout"
                        )
                        self.core.log(f"TIMEOUT after {timeout}s: {command}")
                        self.core.kill_process_group(proc)
                    elif self._idle_timeout > 0 and now - last_output >= self._idle_timeout:
                        idle_timed_out = True
                        self._last_failure_reason = (
                            "verification_idle_timeout"
                            if phase == "verification"
                            else "command_idle_timeout"
                        )
                        self.core.log(
                            f"IDLE TIMEOUT after {self._idle_timeout}s: {command}"
                        )
                        self.core.kill_process_group(proc)

                try:
                    item = lines.get(timeout=0.25)
                    if item is None:
                        reader_done = True
                    else:
                        last_output = time.monotonic()
                        live_output.emit(item)
                        chunks.append(item)
                        total_chars += len(item)
                        while total_chars > MAX_OUTPUT and chunks:
                            removed = chunks.pop(0)
                            total_chars -= len(removed)
                except queue.Empty:
                    pass

                now = time.monotonic()
                if now - last_progress >= PROGRESS_INTERVAL:
                    last_progress = now
                    self._emit(
                        {
                            "event": "command_heartbeat",
                            "phase": phase,
                            "index": self._command_index,
                            "total": self._command_count,
                            "command": command,
                            "pid": proc.pid,
                            "elapsed_seconds": round(now - started, 3),
                            "seconds_since_output": round(now - last_output, 3),
                            "updated_at": self.core.now_iso(),
                        }
                    )

                if proc.poll() is not None and reader_done:
                    break
                if (
                    timed_out or idle_timed_out or task_timed_out
                ) and proc.poll() is not None:
                    while True:
                        try:
                            item = lines.get_nowait()
                        except queue.Empty:
                            break
                        if item is None:
                            continue
                        live_output.emit(item)
                        chunks.append(item)
                    break
        finally:
            live_output.finish()
            with self._active_lock:
                if self._active_process is proc:
                    self._active_process = None
            thread.join(timeout=1)
            if proc.stdout is not None:
                proc.stdout.close()

        exit_code = proc.returncode if proc.returncode is not None else 124
        if timed_out or idle_timed_out or task_timed_out:
            exit_code = 124
        elapsed = time.monotonic() - started
        result = {
            "command": command,
            "exit_code": exit_code,
            "output": "".join(chunks),
            "elapsed_seconds": round(elapsed, 3),
            "timed_out": timed_out,
            "idle_timed_out": idle_timed_out,
            "task_timed_out": task_timed_out,
        }
        self.core.log(f"exec finished exit={exit_code} elapsed={elapsed:.1f}s: {command}")
        self._emit(
            {
                "event": "command_finished",
                "phase": phase,
                "index": self._command_index,
                "total": self._command_count,
                "command": command,
                "exit_code": exit_code,
                "elapsed_seconds": round(elapsed, 3),
                "timed_out": timed_out,
                "idle_timed_out": idle_timed_out,
                "task_timed_out": task_timed_out,
                "finished_at": self.core.now_iso(),
            }
        )
        return result

    def process_task(
        self,
        task: dict[str, Any],
        *,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        validate_task(task)
        idle_timeout = idle_timeout_for(task)
        task_timeout = task_timeout_for(task)
        digest = task_digest(task)
        self._progress = progress
        self._idle_timeout = idle_timeout
        self._deadline = time.monotonic() + task_timeout
        self._command_index = 0
        self._primary_count = len(task.get("commands", []))
        self._command_count = self._primary_count + len(task.get("verify_commands", []))
        self._last_failure_reason = None

        original_run_command = self.core.run_command
        self.core.run_command = self.run_command
        self._emit(
            {
                "event": "task_started",
                "task_id": task["id"],
                "task_digest": digest,
                "idle_timeout": idle_timeout,
                "task_timeout": task_timeout,
                "started_at": self.core.now_iso(),
            }
        )
        try:
            result = self.core.process_task(task)
            result["task_digest"] = digest
            result["idle_timeout"] = idle_timeout
            result["task_timeout"] = task_timeout
            if self._last_failure_reason and result.get("status") != "done":
                result["failure_reason"] = self._last_failure_reason
            self._emit(
                {
                    "event": "task_finished",
                    "task_id": task["id"],
                    "task_digest": digest,
                    "status": result.get("status"),
                    "failure_reason": result.get("failure_reason"),
                    "finished_at": result.get("finished_at", self.core.now_iso()),
                }
            )
            return result
        finally:
            self.core.run_command = original_run_command
            self._progress = None
            self._deadline = None
