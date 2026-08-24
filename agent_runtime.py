#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from agent_process import BoundedTextBuffer, spawn_shell, start_output_pump

ProgressCallback = Callable[[dict[str, Any]], None]

_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
DEFAULT_IDLE_TIMEOUT = 300
MAX_IDLE_TIMEOUT = 900
DEFAULT_TASK_TIMEOUT = 1800
MAX_TASK_TIMEOUT = 1800
TASK_FINALIZATION_RESERVE = 60
DEFAULT_MEMORY_LIMIT_MB = 4096
MAX_MEMORY_LIMIT_MB = 16384
MEMORY_SAMPLE_INTERVAL = 2.0
PROGRESS_INTERVAL = 30
MAX_OUTPUT = 60000
MAX_PROGRESS_MARKER = 4096
MAX_PROGRESS_TEXT = 256
MAX_PROGRESS_METRICS = 16
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
    for field in (
        "writes",
        "deletes",
        "commands",
        "verify_commands",
        "steps",
        "verify_steps",
    ):
        if field in task and not isinstance(task[field], list):
            raise ValueError(f"{field} must be a list")
    core_module = __import__("agent_core")
    stage_plan = core_module.stage_plan_for(task)
    command_timeout = core_module.command_timeout_for(task)
    idle_timeout_for(task)
    task_timeout = task_timeout_for(task)
    memory_limit_for(task)
    for stage in stage_plan:
        stage_timeout = int(stage.get("stage_timeout", command_timeout))
        if stage_timeout + TASK_FINALIZATION_RESERVE > task_timeout:
            raise ValueError(
                f"stage {stage['stage_name']!r} timeout {stage_timeout}s cannot fit "
                f"inside task_timeout={task_timeout}s with "
                f"{TASK_FINALIZATION_RESERVE}s finalization reserve"
            )


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


def memory_limit_for(task: dict[str, Any]) -> int:
    return _bounded_int(
        task,
        "memory_limit_mb",
        DEFAULT_MEMORY_LIMIT_MB,
        0,
        MAX_MEMORY_LIMIT_MB,
    )


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


def _safe_command(args: list[str], timeout: float = 2.0) -> str | None:
    try:
        completed = subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def parse_mac_vm_stat(text: str, *, page_size: int = 4096) -> dict[str, int]:
    page_size_match = re.search(r"page size of\s+(\d+)\s+bytes", text, re.IGNORECASE)
    if page_size_match is not None:
        parsed_page_size = int(page_size_match.group(1))
        if parsed_page_size > 0:
            page_size = parsed_page_size
    pages: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^Pages ([^:]+):\s+(\d+)", line)
        if match:
            pages[match.group(1).lower()] = int(match.group(2))
    available = sum(pages.get(name, 0) for name in ("free", "inactive", "speculative"))
    used = max(0, sum(pages.values()) - available)
    return {
        "available_bytes": available * page_size,
        "used_bytes": used * page_size,
    }


def parse_mac_swapusage(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for name, number, unit in re.findall(
        r"(total|used|free)\s*=\s*([0-9.]+)([MG])B?", text
    ):
        multiplier = 1024**2 if unit == "M" else 1024**3
        values[name] = int(float(number) * multiplier)
    return values


def parse_mac_top_cpu(text: str) -> float | None:
    match = re.search(
        r"CPU usage:\s*([0-9.]+)%\s*user,\s*([0-9.]+)%\s*sys,\s*([0-9.]+)%\s*idle",
        text,
    )
    if match is None:
        return None
    try:
        return round(float(match.group(1)) + float(match.group(2)), 2)
    except ValueError:
        return None


def normalize_host_cpu_percent(total_cpu_percent: float, logical_cpu_count: int) -> float:
    """Normalize summed per-process CPU percentages to host utilization."""
    divisor = max(1, logical_cpu_count)
    return round(max(0.0, min(100.0, total_cpu_percent / divisor)), 2)


def parse_mac_ps_cpu(text: str, logical_cpu_count: int) -> float | None:
    total = 0.0
    parsed = False
    for line in text.splitlines():
        try:
            value = float(line.strip())
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        total += value
        parsed = True
    if not parsed:
        return None
    return normalize_host_cpu_percent(total, logical_cpu_count)


def parse_process_group_ps(text: str, process_group: int) -> dict[str, Any]:
    cpu = 0.0
    rss_kb = 0
    processes = 0
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        try:
            if int(fields[1]) != process_group:
                continue
            cpu += float(fields[2])
            rss_kb += int(fields[3])
            processes += 1
        except (TypeError, ValueError):
            continue
    if processes == 0:
        return {}
    return {
        "command_cpu_percent": round(cpu, 2),
        "command_rss_mb": round(rss_kb / 1024, 2),
        "command_children": max(0, processes - 1),
    }


def collect_host_telemetry() -> dict[str, Any]:
    telemetry: dict[str, Any] = {}
    try:
        telemetry["host_load_1m"] = round(float(os.getloadavg()[0]), 2)
    except (AttributeError, OSError, IndexError, TypeError, ValueError):
        pass

    if platform.system() == "Darwin":
        total_raw = _safe_command(["sysctl", "-n", "hw.memsize"])
        vm_stat = _safe_command(["vm_stat"])
        if total_raw and vm_stat:
            try:
                total = int(total_raw.strip())
                parsed = parse_mac_vm_stat(vm_stat)
                available = parsed["available_bytes"]
                telemetry["host_memory_available_mb"] = round(available / 1024**2, 2)
                telemetry["host_memory_used_percent"] = round(
                    max(0.0, min(100.0, (total - available) / total * 100)), 2
                )
            except (TypeError, ValueError, ZeroDivisionError, KeyError):
                pass
        swap = _safe_command(["sysctl", "-n", "vm.swapusage"])
        if swap:
            parsed_swap = parse_mac_swapusage(swap)
            if "used" in parsed_swap:
                telemetry["host_swap_used_mb"] = round(parsed_swap["used"] / 1024**2, 2)
            if "total" in parsed_swap:
                telemetry["host_swap_total_mb"] = round(parsed_swap["total"] / 1024**2, 2)
        cpu_text = _safe_command(["top", "-l", "1", "-n", "0"])
        top_cpu = parse_mac_top_cpu(cpu_text or "")
        if top_cpu is not None:
            telemetry["host_cpu_percent"] = top_cpu
        else:
            cpu_text = _safe_command(["ps", "-A", "-o", "%cpu="])
        if cpu_text and "host_cpu_percent" not in telemetry:
            host_cpu = parse_mac_ps_cpu(cpu_text, os.cpu_count() or 1)
            if host_cpu is not None:
                telemetry["host_cpu_percent"] = host_cpu
    else:
        try:
            memory: dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition(":")
                fields = value.split()
                if fields and fields[0].isdigit():
                    memory[key] = int(fields[0]) * 1024
            total = memory.get("MemTotal")
            available = memory.get("MemAvailable")
            if total and available is not None:
                telemetry["host_memory_available_mb"] = round(available / 1024**2, 2)
                telemetry["host_memory_used_percent"] = round(
                    (total - available) / total * 100, 2
                )
            swap_total = memory.get("SwapTotal")
            swap_free = memory.get("SwapFree")
            if swap_total is not None and swap_free is not None:
                telemetry["host_swap_total_mb"] = round(swap_total / 1024**2, 2)
                telemetry["host_swap_used_mb"] = round(
                    (swap_total - swap_free) / 1024**2, 2
                )
        except (OSError, UnicodeError, ValueError):
            pass
    return telemetry


def collect_process_telemetry(pid: int) -> dict[str, Any]:
    try:
        process_group = os.getpgid(pid)
    except (OSError, ProcessLookupError):
        return {}
    text = _safe_command(["ps", "-axo", "pid=,pgid=,%cpu=,rss="])
    return parse_process_group_ps(text, process_group) if text else {}


def collect_telemetry(pid: int) -> dict[str, Any]:
    telemetry: dict[str, Any] = {}
    try:
        telemetry.update(collect_host_telemetry())
    except Exception:
        pass
    try:
        telemetry.update(collect_process_telemetry(pid))
    except Exception:
        pass
    return telemetry


def sample_process_group_rss_mb(process_group: int) -> float | None:
    text = _safe_command(["ps", "-axo", "pid=,pgid=,%cpu=,rss="], timeout=5.0)
    if not text:
        return None
    telemetry = parse_process_group_ps(text, process_group)
    value = telemetry.get("command_rss_mb")
    return float(value) if isinstance(value, (int, float)) else None


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
        started = time.monotonic()
        last_output = started
        last_progress = started
        timed_out = False
        idle_timed_out = False
        task_timed_out = False
        memory_limited = False
        command_failure_reason: str | None = None
        current_rss_mb: float | None = None
        peak_rss_mb: float | None = None
        over_limit_samples = 0
        memory_measurement_warned = False
        next_memory_sample = started

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
                    "task_timed_out": False,
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
                        "task_timed_out": False,
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

        self.core.log(f"exec: {command}")
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
        output = BoundedTextBuffer(MAX_OUTPUT)
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
                        self.core.log(f"TIMEOUT after {timeout}s: {command}")
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
                            f"IDLE TIMEOUT after {self._idle_timeout}s: {command}"
                        )
                        self.core.kill_process_group(proc)

                if (
                    self._memory_limit_mb > 0
                    and not memory_limited
                    and proc.poll() is None
                    and now >= next_memory_sample
                ):
                    try:
                        current_rss_mb = self._rss_sampler(process_group)
                    except Exception:
                        current_rss_mb = None
                    next_memory_sample = time.monotonic() + self._memory_sample_interval
                    if current_rss_mb is None:
                        if not memory_measurement_warned:
                            self.core.log(
                                "RSS memory measurement unavailable; continuing with time watchdogs"
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
                                f"at {current_rss_mb:.1f} MB: {command}"
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
                                    "message": marker.get("message"),
                                    "progress_current": marker.get("current"),
                                    "progress_total": marker.get("total"),
                                    "metrics": marker.get("metrics"),
                                    "last_progress_at": self._last_progress_at,
                                    "last_progress_message": marker.get("message"),
                                }
                            )
                        live_output.emit(item)
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
                    try:
                        heartbeat.update(collect_telemetry(proc.pid))
                    except Exception:
                        pass
                    self._emit(heartbeat)

                if proc.poll() is not None and reader_done:
                    break
        finally:
            live_output.finish()
            pump.stop()
            with self._active_lock:
                if self._active_process is proc:
                    self._active_process = None

        exit_code = proc.returncode if proc.returncode is not None else 124
        if timed_out or idle_timed_out or task_timed_out or memory_limited:
            exit_code = 124
        elapsed = time.monotonic() - started
        result = {
            "command": command,
            "exit_code": exit_code,
            "output": output.text(),
            "elapsed_seconds": round(elapsed, 3),
            "timed_out": timed_out,
            "idle_timed_out": idle_timed_out,
            "task_timed_out": task_timed_out,
            "memory_limit_mb": self._memory_limit_mb,
            "memory_limited": memory_limited,
            "peak_rss_mb": peak_rss_mb,
        }
        if current_rss_mb is not None:
            result["current_rss_mb"] = current_rss_mb
        if command_failure_reason is not None:
            result["failure_reason"] = command_failure_reason
        self.core.log(f"exec finished exit={exit_code} elapsed={elapsed:.1f}s: {command}")
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
            "task_timed_out": task_timed_out,
            "memory_limited": memory_limited,
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
        self._progress = progress
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
            self._progress = None
            self._deadline = None
            self._stage_plan = []
            self._domain_progress = None
            self._last_progress_at = None
