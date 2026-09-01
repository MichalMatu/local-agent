#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import queue
import re
import subprocess
import threading
import time
from typing import Any, Callable

from agent_process import (
    BoundedTextBuffer,
    spawn_shell,
    start_output_pump,
    terminate_remaining_process_group,
    unregister_process,
)

from local_agent.runtime.task_contract import (
    DEFAULT_IDLE_TIMEOUT as DEFAULT_IDLE_TIMEOUT,
    DEFAULT_MEMORY_LIMIT_MB as DEFAULT_MEMORY_LIMIT_MB,
    DEFAULT_TASK_TIMEOUT as DEFAULT_TASK_TIMEOUT,
    MAX_COMMAND_CHARS as MAX_COMMAND_CHARS,
    MAX_IDLE_TIMEOUT as MAX_IDLE_TIMEOUT,
    MAX_MEMORY_LIMIT_MB as MAX_MEMORY_LIMIT_MB,
    MAX_PATCH_BYTES as MAX_PATCH_BYTES,
    MAX_TASK_FILE_BYTES as MAX_TASK_FILE_BYTES,
    MAX_TASK_LIST_ITEMS as MAX_TASK_LIST_ITEMS,
    MAX_TASK_PATH_CHARS as MAX_TASK_PATH_CHARS,
    MAX_TASK_TIMEOUT as MAX_TASK_TIMEOUT,
    MAX_TOTAL_WRITE_BYTES as MAX_TOTAL_WRITE_BYTES,
    MAX_WRITE_BYTES as MAX_WRITE_BYTES,
    TASK_FINALIZATION_RESERVE as TASK_FINALIZATION_RESERVE,
    _TASK_ID_RE as _TASK_ID_RE,
    _bounded_int as _bounded_int,
    idle_timeout_for as idle_timeout_for,
    memory_limit_for as memory_limit_for,
    task_digest as task_digest,
    task_timeout_for as task_timeout_for,
    validate_task as validate_task,
)
from local_agent.runtime import telemetry as runtime_telemetry
from local_agent.runtime.output import (
    LIVE_DIFF_MAX_CHARS as LIVE_DIFF_MAX_CHARS,
    LIVE_DIFF_MAX_LINES as LIVE_DIFF_MAX_LINES,
    SUMMARY_FAILURE_TAIL_CHARS,
    LiveCommandOutput,
    emit_summary_failure_tail,
)
from local_agent.runtime.telemetry import (
    collect_host_telemetry as collect_host_telemetry,
    collect_process_telemetry as collect_process_telemetry,
    collect_telemetry,
    normalize_host_cpu_percent as normalize_host_cpu_percent,
    parse_mac_ps_cpu as parse_mac_ps_cpu,
    parse_mac_swapusage as parse_mac_swapusage,
    parse_mac_top_cpu as parse_mac_top_cpu,
    parse_mac_vm_stat as parse_mac_vm_stat,
    parse_process_group_ps as parse_process_group_ps,
)

# Compatibility seam: existing tests/callers may patch agent_runtime._safe_command.
_safe_command = runtime_telemetry._safe_command

def sample_process_group_rss_mb(process_group: int) -> float | None:
    text = _safe_command(["ps", "-axo", "pid=,pgid=,%cpu=,rss="], timeout=5.0)
    if not text:
        return None
    telemetry = parse_process_group_ps(text, process_group)
    value = telemetry.get("command_rss_mb")
    return float(value) if isinstance(value, (int, float)) else None

ProgressCallback = Callable[[dict[str, Any]], None]

MEMORY_SAMPLE_INTERVAL = 2.0
PROGRESS_INTERVAL = 30
MAX_OUTPUT = 60000
MAX_PROGRESS_MARKER = 4096
MAX_PROGRESS_TEXT = 256
MAX_PROGRESS_METRICS = 16
PROGRESS_EVENT_QUEUE_CAPACITY = 64
PROGRESS_FLUSH_TIMEOUT = 65.0
def parse_progress_marker(line: str) -> dict[str, Any] | None:
    prefix = "[AGENT_PROGRESS] "
    if not line.startswith(prefix) or len(line) > MAX_PROGRESS_MARKER:
        return None
    try:
        payload = json.loads(line[len(prefix):].strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    result: dict[str, Any] = {}
    for field in ("stage_name", "message"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            result[field] = value.strip()[:MAX_PROGRESS_TEXT]
    if "stage_name" not in result and "message" not in result:
        return None

    for field in ("current", "total"):
        value = payload.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if math.isfinite(float(value)) and abs(float(value)) <= 1_000_000_000:
                result[field] = value

    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        safe_metrics: dict[str, str | int | float | bool] = {}
        for key, value in list(metrics.items())[:MAX_PROGRESS_METRICS]:
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", key):
                continue
            if isinstance(value, (str, int, float, bool)):
                if isinstance(value, float) and not math.isfinite(value):
                    continue
                safe_metrics[key] = value
        if safe_metrics:
            result["metrics"] = safe_metrics
    return result


class ProgressDispatcher:
    """Keep progress publication outside command watchdog loops with bounded handoff."""

    def __init__(self, callback: ProgressCallback, log: Callable[[str], None]) -> None:
        self._callback = callback
        self._log = log
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(
            maxsize=PROGRESS_EVENT_QUEUE_CAPACITY
        )
        self._closed = False
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="local-agent-progress",
        )
        self._thread.start()

    def _run(self) -> None:
        while True:
            event = self._queue.get()
            try:
                if event is None:
                    return
                try:
                    self._callback(event)
                except Exception as exc:
                    self._log(
                        f"progress callback failed: {type(exc).__name__}: {exc}"
                    )
            finally:
                self._queue.task_done()

    def submit(self, event: dict[str, Any]) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(event)
            return
        except queue.Full:
            pass
        try:
            dropped = self._queue.get_nowait()
            self._queue.task_done()
            if dropped is None:
                self._closed = True
                return
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self._log("progress event dropped because the bounded queue is full")

    def close(self, timeout: float = PROGRESS_FLUSH_TIMEOUT) -> None:
        if self._closed:
            return
        self._closed = True
        while True:
            try:
                self._queue.put_nowait(None)
                break
            except queue.Full:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    continue
        self._thread.join(timeout=max(0.0, timeout))
        if self._thread.is_alive():
            self._log("progress publication did not drain within its bounded deadline")


class TelemetrySampler:
    """Collect optional host telemetry without delaying command watchdog checks."""

    def __init__(self, pid: int) -> None:
        self._pid = pid
        self._latest: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="local-agent-telemetry",
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                sample = collect_telemetry(self._pid)
            except Exception:
                sample = {}
            with self._lock:
                self._latest = sample
            self._stop.wait(PROGRESS_INTERVAL)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._latest)

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=0.1)


class RssSampler:
    """Sample process-group RSS without blocking command timeout enforcement."""

    def __init__(
        self,
        process_group: int,
        sampler: Callable[[int], float | None],
        interval: float,
    ) -> None:
        self._process_group = process_group
        self._sampler = sampler
        self._interval = interval
        self._latest: float | None = None
        self._generation = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="local-agent-rss",
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                sample = self._sampler(self._process_group)
            except Exception:
                sample = None
            with self._lock:
                self._latest = sample
                self._generation += 1
            self._stop.wait(self._interval)

    def snapshot(self) -> tuple[int, float | None]:
        with self._lock:
            return self._generation, self._latest

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=0.1)


class RuntimeExecutor:
    def __init__(
        self,
        core_module: Any,
        *,
        rss_sampler: Callable[[int], float | None] = sample_process_group_rss_mb,
        memory_sample_interval: float = MEMORY_SAMPLE_INTERVAL,
    ) -> None:
        self.core = core_module
        self._rss_sampler = rss_sampler
        self._memory_sample_interval = max(0.05, float(memory_sample_interval))
        self._active_process: subprocess.Popen[str] | None = None
        self._active_lock = threading.Lock()
        self._progress: ProgressCallback | None = None
        self._deadline: float | None = None
        self._idle_timeout = DEFAULT_IDLE_TIMEOUT
        self._memory_limit_mb = DEFAULT_MEMORY_LIMIT_MB
        self._command_index = 0
        self._command_count = 0
        self._primary_count = 0
        self._last_failure_reason: str | None = None
        self._stage_plan: list[dict[str, Any]] = []
        self._domain_progress: dict[str, Any] | None = None
        self._last_progress_at: str | None = None

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
        if proc is None:
            return False
        self.core.kill_process_group(proc)
        return True

    def _phase(self) -> str:
        return "commands" if self._command_index <= self._primary_count else "verification"

    def run_command(
        self,
        command: str,
        timeout: int,
        *,
        stage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._domain_progress = None
        self._last_progress_at = None
        self._command_index += 1
        phase = self._phase()
        if stage is None:
            stage = (
                self._stage_plan[self._command_index - 1]
                if self._command_index <= len(self._stage_plan)
                else {
                    "stage_name": (
                        f"command-{self._command_index}"
                        if phase == "commands"
                        else f"verification-{self._command_index - self._primary_count}"
                    ),
                    "stage_index": self._command_index,
                    "stage_total": self._command_count,
                    "stage_phase": phase,
                }
            )
        output_policy = str(stage.get("output_policy", "stream"))
        if output_policy not in self.core.OUTPUT_POLICIES:
            raise ValueError(f"unsupported output_policy: {output_policy!r}")

        started = time.monotonic()
        last_output = started
        last_progress = started
        timed_out = False
        idle_timed_out = False
        memory_limited = False
        background_process_leak = False
        direct_process_finished = False
        command_failure_reason: str | None = None
        current_rss_mb: float | None = None
        peak_rss_mb: float | None = None
        over_limit_samples = 0
        memory_measurement_warned = False
        last_memory_generation = 0

        budget_remaining: float | None = None
        if self._deadline is not None:
            budget_remaining = max(0.0, self._deadline - started)
            required_budget = float(timeout + TASK_FINALIZATION_RESERVE)
            if budget_remaining < required_budget:
                self._last_failure_reason = "task_budget_exhausted"
                elapsed = time.monotonic() - started
                result = {
                    "command": command,
                    "exit_code": 125,
                    "output": "",
                    "elapsed_seconds": round(elapsed, 3),
                    "timed_out": False,
                    "idle_timed_out": False,
                    "memory_limited": False,
                    "not_started": True,
                    "budget_exhausted": True,
                    "budget_remaining_seconds": round(budget_remaining, 3),
                    "required_budget_seconds": round(required_budget, 3),
                }
                self.core.log(
                    f"TASK BUDGET EXHAUSTED before stage {stage['stage_name']}: "
                    f"remaining={budget_remaining:.1f}s required={required_budget:.1f}s"
                )
                self._emit(
                    {
                        "event": "command_finished",
                        "phase": phase,
                        "index": self._command_index,
                        "total": self._command_count,
                        "command": command,
                        "exit_code": 125,
                        "elapsed_seconds": round(elapsed, 3),
                        "timed_out": False,
                        "idle_timed_out": False,
                        "memory_limited": False,
                        "not_started": True,
                        "budget_exhausted": True,
                        "budget_remaining_seconds": round(budget_remaining, 3),
                        "required_budget_seconds": round(required_budget, 3),
                        "finished_at": self.core.now_iso(),
                        **stage,
                    }
                )
                return result

        command_descriptor = self.core.command_log_descriptor(
            command,
            {"name": stage.get("stage_name", "")},
        )
        self.core.log(f"exec: {command_descriptor}")
        proc = spawn_shell(command, cwd=self.core.WORK, env=self.core.ENV)
        process_group = proc.pid
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
                "memory_limit_mb": self._memory_limit_mb,
                "started_at": self.core.now_iso(),
                **stage,
            }
        )

        pump = start_output_pump(proc)
        telemetry_sampler = TelemetrySampler(proc.pid)
        rss_sampler = RssSampler(
            process_group,
            self._rss_sampler,
            self._memory_sample_interval,
        )
        output = BoundedTextBuffer(MAX_OUTPUT)
        failure_tail = BoundedTextBuffer(SUMMARY_FAILURE_TAIL_CHARS)
        captured_output_chars = 0
        reader_done = False
        live_output = LiveCommandOutput()

        try:
            while True:
                now = time.monotonic()
                elapsed = now - started
                if proc.poll() is None:
                    if elapsed >= timeout and not timed_out:
                        timed_out = True
                        self._last_failure_reason = (
                            "verification_timeout" if phase == "verification" else "command_timeout"
                        )
                        self.core.log(f"TIMEOUT after {timeout}s: {command_descriptor}")
                        self.core.kill_process_group(proc)
                    elif (
                        self._idle_timeout > 0
                        and now - last_output >= self._idle_timeout
                        and not idle_timed_out
                    ):
                        idle_timed_out = True
                        self._last_failure_reason = (
                            "verification_idle_timeout"
                            if phase == "verification"
                            else "command_idle_timeout"
                        )
                        self.core.log(
                            f"IDLE TIMEOUT after {self._idle_timeout}s: {command_descriptor}"
                        )
                        self.core.kill_process_group(proc)

                if proc.poll() is not None and not direct_process_finished:
                    direct_process_finished = True
                    background_process_leak = terminate_remaining_process_group(
                        proc,
                        self.core.log,
                    )
                    if background_process_leak:
                        command_failure_reason = (
                            "verification_background_process_leak"
                            if phase == "verification"
                            else "command_background_process_leak"
                        )
                        self._last_failure_reason = command_failure_reason

                if (
                    self._memory_limit_mb > 0
                    and not memory_limited
                    and proc.poll() is None
                ):
                    generation, sampled_rss_mb = rss_sampler.snapshot()
                    if generation != last_memory_generation:
                        last_memory_generation = generation
                        current_rss_mb = sampled_rss_mb
                        if current_rss_mb is None:
                            if not memory_measurement_warned:
                                self.core.log(
                                    "RSS memory measurement unavailable; "
                                    "continuing with time watchdogs"
                                )
                                memory_measurement_warned = True
                        else:
                            peak_rss_mb = (
                                current_rss_mb
                                if peak_rss_mb is None
                                else max(peak_rss_mb, current_rss_mb)
                            )
                            if current_rss_mb > self._memory_limit_mb:
                                over_limit_samples += 1
                            else:
                                over_limit_samples = 0
                            if over_limit_samples >= 2:
                                memory_limited = True
                                command_failure_reason = (
                                    "verification_memory_limit"
                                    if phase == "verification"
                                    else "command_memory_limit"
                                )
                                self._last_failure_reason = command_failure_reason
                                self.core.log(
                                    f"MEMORY LIMIT after {over_limit_samples} samples "
                                    f"at {current_rss_mb:.1f} MB: {command_descriptor}"
                                )
                                self.core.kill_process_group(proc)

                try:
                    item = pump.queue.get(timeout=0.25)
                    if item is None:
                        reader_done = True
                    else:
                        last_output = time.monotonic()
                        marker = parse_progress_marker(item)
                        if marker is not None:
                            self._domain_progress = marker
                            self._last_progress_at = self.core.now_iso()
                            self._emit(
                                {
                                    "event": "stage_progress",
                                    "stage_progress": marker,
                                    "phase": phase,
                                    "index": self._command_index,
                                    "total": self._command_count,
                                    "command": command,
                                    "pid": proc.pid,
                                    "stage_name": marker.get("stage_name", stage["stage_name"]),
                                    "stage_index": stage["stage_index"],
                                    "stage_total": stage["stage_total"],
                                    "stage_phase": stage["stage_phase"],
                                    **(
                                        {
                                            "verification_level": stage[
                                                "verification_level"
                                            ]
                                        }
                                        if "verification_level" in stage
                                        else {}
                                    ),
                                    "message": marker.get("message"),
                                    "progress_current": marker.get("current"),
                                    "progress_total": marker.get("total"),
                                    "metrics": marker.get("metrics"),
                                    "last_progress_at": self._last_progress_at,
                                    "last_progress_message": marker.get("message"),
                                }
                            )
                        captured_output_chars += len(item)
                        failure_tail.append(item)
                        if output_policy == "stream":
                            live_output.emit(item)
                        elif marker is not None:
                            message = marker.get("message") or marker.get("stage_name") or "progress"
                            print(f"[CMD] [progress] {message}", flush=True)
                        output.append(item)
                except queue.Empty:
                    pass

                now = time.monotonic()
                if now - last_progress >= PROGRESS_INTERVAL:
                    last_progress = now
                    heartbeat = {
                        "event": "command_heartbeat",
                        "phase": phase,
                        "index": self._command_index,
                        "total": self._command_count,
                        "command": command,
                        "pid": proc.pid,
                        "elapsed_seconds": round(now - started, 3),
                        "seconds_since_output": round(now - last_output, 3),
                        "updated_at": self.core.now_iso(),
                        **stage,
                    }
                    if self._deadline is not None:
                        heartbeat["task_budget_remaining_seconds"] = round(
                            max(0.0, self._deadline - now), 3
                        )
                    if self._domain_progress is not None:
                        heartbeat["stage_progress"] = dict(self._domain_progress)
                        heartbeat["last_progress_at"] = self._last_progress_at
                        heartbeat["last_progress_message"] = self._domain_progress.get(
                            "message"
                        )
                    if current_rss_mb is not None:
                        heartbeat["current_rss_mb"] = current_rss_mb
                    if peak_rss_mb is not None:
                        heartbeat["peak_rss_mb"] = peak_rss_mb
                    heartbeat.update(telemetry_sampler.snapshot())
                    self._emit(heartbeat)

                if direct_process_finished and reader_done:
                    break
        finally:
            if proc.poll() is None:
                self.core.kill_process_group(proc)
            live_output.finish()
            pump.stop()
            telemetry_sampler.stop()
            rss_sampler.stop()
            with self._active_lock:
                if self._active_process is proc:
                    self._active_process = None
            unregister_process(proc)

        exit_code = proc.returncode if proc.returncode is not None else 124
        if timed_out or idle_timed_out or memory_limited:
            exit_code = 124
        elif background_process_leak:
            exit_code = 126
        elapsed = time.monotonic() - started
        if output_policy == "summary":
            if exit_code == 0:
                self.core.log(
                    "output summary "
                    f"stage={stage['stage_name']} exit=0 "
                    f"captured_chars={captured_output_chars}"
                )
            else:
                self.core.log(
                    "output summary "
                    f"stage={stage['stage_name']} exit={exit_code} "
                    f"captured_chars={captured_output_chars}; showing bounded tail"
                )
                emit_summary_failure_tail(
                    failure_tail.text(),
                    truncated=failure_tail.truncated,
                )
        result = {
            "command": command,
            "exit_code": exit_code,
            "output": output.text(),
            "elapsed_seconds": round(elapsed, 3),
            "timed_out": timed_out,
            "idle_timed_out": idle_timed_out,
            "memory_limit_mb": self._memory_limit_mb,
            "memory_limited": memory_limited,
            "background_process_leak": background_process_leak,
            "peak_rss_mb": peak_rss_mb,
            "output_policy": output_policy,
            "captured_output_chars": captured_output_chars,
            "output_truncated": output.truncated,
        }
        if current_rss_mb is not None:
            result["current_rss_mb"] = current_rss_mb
        if command_failure_reason is not None:
            result["failure_reason"] = command_failure_reason
        self.core.log(f"exec finished exit={exit_code} elapsed={elapsed:.1f}s: {command_descriptor}")
        finished_event = {
            "event": "command_finished",
            "phase": phase,
            "index": self._command_index,
            "total": self._command_count,
            "command": command,
            "exit_code": exit_code,
            "elapsed_seconds": round(elapsed, 3),
            "timed_out": timed_out,
            "idle_timed_out": idle_timed_out,
            "memory_limited": memory_limited,
            "background_process_leak": background_process_leak,
            "finished_at": self.core.now_iso(),
            **stage,
        }
        if peak_rss_mb is not None:
            finished_event["peak_rss_mb"] = peak_rss_mb
        if command_failure_reason is not None:
            finished_event["failure_reason"] = command_failure_reason
        self._emit(finished_event)
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
        memory_limit_mb = memory_limit_for(task)
        digest = task_digest(task)
        progress_dispatcher = (
            ProgressDispatcher(progress, self.core.log) if progress is not None else None
        )
        self._progress = progress_dispatcher.submit if progress_dispatcher else None
        self._idle_timeout = idle_timeout
        self._memory_limit_mb = memory_limit_mb
        self._deadline = time.monotonic() + task_timeout
        self._command_index = 0
        self._stage_plan = self.core.stage_plan_for(task)
        self._primary_count = sum(
            1 for stage in self._stage_plan if stage["stage_phase"] == "commands"
        )
        self._command_count = len(self._stage_plan)
        self._domain_progress = None
        self._last_progress_at = None
        self._last_failure_reason = None

        self._emit(
            {
                "event": "task_started",
                "task_id": task["id"],
                "task_digest": digest,
                "idle_timeout": idle_timeout,
                "task_timeout": task_timeout,
                "memory_limit_mb": memory_limit_mb,
                "started_at": self.core.now_iso(),
            }
        )
        try:
            result = self.core.process_task(task, command_runner=self.run_command)
            result["task_digest"] = digest
            result["idle_timeout"] = idle_timeout
            result["task_timeout"] = task_timeout
            result["memory_limit_mb"] = memory_limit_mb
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
            if progress_dispatcher is not None:
                progress_dispatcher.close()
            self._progress = None
            self._deadline = None
            self._stage_plan = []
            self._domain_progress = None
            self._last_progress_at = None
