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
                        print(f"[CMD] {item}", end="", flush=True)
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
                        print(f"[CMD] {item}", end="", flush=True)
                        chunks.append(item)
                    break
        finally:
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
