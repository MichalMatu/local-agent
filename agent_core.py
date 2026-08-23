#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HOME = Path.home()
CONTROL = HOME / "agent-workspace" / "control"
WORK = HOME / "agent-workspace" / "work"
CHECKPOINTS = HOME / "agent-workspace" / "checkpoints"
CONTROL_BRANCH = "agent-control"

POLL_SECONDS = 15
COMMAND_TIMEOUT = 7200
MAX_COMMAND_TIMEOUT = 21600
MAX_OUTPUT = 60000

BASE_PATH = [
    str(HOME / ".platformio" / "penv" / "bin"),
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
]
ENV = os.environ.copy()
ENV["PATH"] = ":".join(BASE_PATH + [ENV.get("PATH", "")])

_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    print(f"[{now_iso()}] {message}", flush=True)


def bounded(text: str, limit: int = MAX_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    return f"[... truncated {len(text) - limit} chars ...]\n{text[-limit:]}"


def process(
    args: list[str],
    cwd: Path,
    timeout: int = 120,
    *,
    input_text: str | None = None,
) -> dict[str, Any]:
    log(f"exec: {' '.join(args)}")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=ENV,
            text=True,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        output = bounded(completed.stdout or "")
        elapsed = time.monotonic() - started
        log(
            f"exec finished exit={completed.returncode} "
            f"elapsed={elapsed:.1f}s: {' '.join(args)}"
        )
        return {
            "exit_code": completed.returncode,
            "output": output,
            "elapsed_seconds": round(elapsed, 3),
        }
    except subprocess.TimeoutExpired as exc:
        output = bounded((exc.stdout or "") if isinstance(exc.stdout, str) else "")
        elapsed = time.monotonic() - started
        log(f"TIMEOUT after {timeout}s: {' '.join(args)}")
        return {
            "exit_code": 124,
            "output": output,
            "elapsed_seconds": round(elapsed, 3),
            "timed_out": True,
        }


def kill_process_group(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return

    log(f"terminating process group pgid={pgid}")
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return

    try:
        proc.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass

    log(f"killing process group pgid={pgid}")
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def run_command(
    command: str,
    timeout: int,
    *,
    stage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    log(f"exec: {command}")
    started = time.monotonic()

    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=WORK,
        env=ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
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
    timed_out = False

    while True:
        elapsed = time.monotonic() - started
        remaining = timeout - elapsed
        if remaining <= 0 and proc.poll() is None:
            timed_out = True
            log(f"TIMEOUT after {timeout}s: {command}")
            kill_process_group(proc)

        try:
            item = lines.get(timeout=0.25 if remaining > 0 else 0.05)
            if item is None:
                reader_done = True
            else:
                print(f"[CMD] {item}", end="", flush=True)
                chunks.append(item)
                total_chars += len(item)
                while total_chars > MAX_OUTPUT and chunks:
                    removed = chunks.pop(0)
                    total_chars -= len(removed)
        except queue.Empty:
            pass

        if proc.poll() is not None and reader_done:
            break

        if timed_out and proc.poll() is not None:
            while True:
                try:
                    item = lines.get_nowait()
                except queue.Empty:
                    break
                if item is None:
                    reader_done = True
                    continue
                print(f"[CMD] {item}", end="", flush=True)
                chunks.append(item)
                total_chars += len(item)
            break

    exit_code = proc.returncode if proc.returncode is not None else 124
    if timed_out:
        exit_code = 124

    elapsed = time.monotonic() - started
    log(f"exec finished exit={exit_code} elapsed={elapsed:.1f}s: {command}")

    return {
        "command": command,
        "exit_code": exit_code,
        "output": "".join(chunks),
        "elapsed_seconds": round(elapsed, 3),
        "timed_out": timed_out,
    }


def validate_branch(branch: str) -> str:
    if (
        not branch
        or not _BRANCH_RE.fullmatch(branch)
        or ".." in branch
        or branch.startswith("/")
        or branch.endswith("/")
    ):
        raise ValueError(f"invalid work_branch: {branch!r}")

    check = process(["git", "check-ref-format", "--branch", branch], CONTROL, timeout=30)
    if check["exit_code"] != 0:
        raise ValueError(f"invalid work_branch: {branch!r}")
    return branch


def sync_control() -> None:
    result = process(["git", "checkout", CONTROL_BRANCH], CONTROL)
    if result["exit_code"] != 0:
        raise RuntimeError(result["output"])

    result = process(["git", "pull", "--rebase", "origin", CONTROL_BRANCH], CONTROL)
    if result["exit_code"] != 0:
        raise RuntimeError(result["output"])


def _run_git_capture(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=WORK,
        env=ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _checkpoint_component(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return clean[:160] or "workspace"


def checkpoint_worktree(task_id: str, *, reason: str) -> dict[str, Any] | None:
    """Persist recoverable dirty workspace state before any destructive cleanup."""
    status_probe = _run_git_capture(["status", "--porcelain=v1", "-z"])
    if status_probe.returncode != 0:
        raise RuntimeError(status_probe.stderr.decode("utf-8", errors="replace"))
    if not status_probe.stdout:
        return None

    head_probe = _run_git_capture(["rev-parse", "HEAD"])
    if head_probe.returncode != 0:
        raise RuntimeError(head_probe.stderr.decode("utf-8", errors="replace"))
    base_head = head_probe.stdout.decode("ascii", errors="strict").strip()

    branch_probe = _run_git_capture(["branch", "--show-current"])
    branch = (
        branch_probe.stdout.decode("utf-8", errors="replace").strip()
        if branch_probe.returncode == 0
        else ""
    )

    task_component = _checkpoint_component(task_id)
    reason_component = _checkpoint_component(reason)
    checkpoint_root = CHECKPOINTS / task_component
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    final_dir = checkpoint_root / f"{time.time_ns()}-{reason_component}"
    temp_dir = final_dir.with_name(final_dir.name + ".tmp")
    temp_dir.mkdir(parents=True, exist_ok=False)

    try:
        patch_path = temp_dir / "tracked.patch"
        with patch_path.open("wb") as patch_file:
            patch = subprocess.run(
                ["git", "diff", "--binary", "--full-index", "HEAD", "--"],
                cwd=WORK,
                env=ENV,
                stdout=patch_file,
                stderr=subprocess.PIPE,
                check=False,
            )
        if patch.returncode != 0:
            raise RuntimeError(patch.stderr.decode("utf-8", errors="replace"))

        untracked_probe = _run_git_capture(
            ["ls-files", "--others", "--exclude-standard", "-z"]
        )
        if untracked_probe.returncode != 0:
            raise RuntimeError(untracked_probe.stderr.decode("utf-8", errors="replace"))

        untracked_files: list[str] = []
        untracked_root = temp_dir / "untracked"
        for raw in untracked_probe.stdout.split(b"\0"):
            if not raw:
                continue
            relative_text = raw.decode("utf-8", errors="surrogateescape")
            relative = Path(relative_text)
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError(f"unsafe untracked path from git: {relative_text!r}")
            source = WORK / relative
            target = untracked_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                os.symlink(os.readlink(source), target)
            elif source.is_file():
                shutil.copy2(source, target)
            else:
                raise RuntimeError(f"unsupported untracked entry: {relative_text!r}")
            untracked_files.append(relative_text)

        short_status = subprocess.run(
            ["git", "status", "--short"],
            cwd=WORK,
            env=ENV,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if short_status.returncode != 0:
            raise RuntimeError(short_status.stdout)

        metadata = {
            "version": 1,
            "task_id": task_id,
            "reason": reason,
            "created_at": now_iso(),
            "base_head": base_head,
            "work_branch": branch,
            "path": str(final_dir),
            "tracked_patch": "tracked.patch",
            "untracked_root": "untracked",
            "untracked_files": untracked_files,
            "status": short_status.stdout,
        }
        (temp_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (temp_dir / "RESTORE.txt").write_text(
            "Checkpoint base HEAD: " + base_head + "\n\n"
            "From a checkout at that base commit:\n"
            "  git apply --binary tracked.patch\n"
            "  cp -a untracked/. <repo>/   # only when untracked/ exists\n",
            encoding="utf-8",
        )
        os.replace(temp_dir, final_dir)
        log(
            f"workspace checkpoint saved: {final_dir} "
            f"untracked={len(untracked_files)}"
        )
        return metadata
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def prepare_work(branch: str, *, task_id: str = "prepare-work") -> None:
    branch = validate_branch(branch)

    safeguard = checkpoint_worktree(task_id, reason="before-prepare")
    if safeguard is not None:
        log(f"preserved dirty workspace before prepare: {safeguard['path']}")

    for args in (
        ["git", "reset", "--hard"],
        ["git", "clean", "-fd"],
        ["git", "fetch", "origin", branch],
        ["git", "checkout", "-B", "agent-work", f"origin/{branch}"],
        ["git", "reset", "--hard", f"origin/{branch}"],
        ["git", "clean", "-fd"],
    ):
        result = process(args, WORK, timeout=300)
        if result["exit_code"] != 0:
            raise RuntimeError(
                f"prepare_work failed: {' '.join(args)}\n{result['output']}"
            )


def cleanup_work() -> None:
    for args in (
        ["git", "reset", "--hard"],
        ["git", "clean", "-fd"],
    ):
        result = process(args, WORK, timeout=300)
        if result["exit_code"] != 0:
            log(f"cleanup warning: {' '.join(args)}\n{result['output']}")


def safe_work_path(relative: str) -> Path:
    if not relative or "\x00" in relative:
        raise ValueError("invalid write path")
    candidate = (WORK / relative).resolve()
    root = WORK.resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError(f"path escapes workspace: {relative!r}")
    return candidate


def apply_patch(patch: str) -> dict[str, Any]:
    if not patch.strip():
        return {"applied": False, "reason": "empty_patch"}

    check = process(
        ["git", "apply", "--check", "--whitespace=nowarn", "-"],
        WORK,
        timeout=120,
        input_text=patch,
    )
    if check["exit_code"] != 0:
        return {
            "applied": False,
            "reason": "git_apply_check_failed",
            "check": check,
        }

    applied = process(
        ["git", "apply", "--whitespace=nowarn", "-"],
        WORK,
        timeout=120,
        input_text=patch,
    )
    return {
        "applied": applied["exit_code"] == 0,
        "apply": applied,
    }


def apply_writes(writes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in writes:
        relative = str(item.get("path", ""))
        content = item.get("content")
        if not isinstance(content, str):
            raise ValueError(f"write content must be string for {relative!r}")
        target = safe_work_path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        results.append(
            {
                "path": relative,
                "bytes": len(content.encode("utf-8")),
            }
        )
        log(f"wrote file: {relative}")
    return results


def apply_deletes(deletes: list[str]) -> list[str]:
    results: list[str] = []
    for relative in deletes:
        target = safe_work_path(str(relative))
        if target.is_dir():
            raise ValueError(f"refusing directory delete: {relative!r}")
        if target.exists():
            target.unlink()
            log(f"deleted file: {relative}")
        results.append(str(relative))
    return results


def command_timeout_for(task: dict[str, Any]) -> int:
    raw = task.get("command_timeout", COMMAND_TIMEOUT)
    try:
        timeout = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"invalid command_timeout: {raw!r}") from None
    if timeout < 1 or timeout > MAX_COMMAND_TIMEOUT:
        raise ValueError(
            f"command_timeout must be 1..{MAX_COMMAND_TIMEOUT}, got {timeout}"
        )
    return timeout


def _validate_stage_items(value: Any, field: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{field} items must be objects")
        name = item.get("name")
        command = item.get("command")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{field} item name must be a non-empty string")
        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"{field} item command must be a non-empty string")


def stage_plan_for(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the one ordered execution plan used by legacy and staged tasks."""
    commands = task.get("commands", [])
    verify_commands = task.get("verify_commands", [])
    steps = task.get("steps", [])
    verify_steps = task.get("verify_steps", [])
    _validate_stage_items(steps, "steps")
    _validate_stage_items(verify_steps, "verify_steps")

    if steps and commands:
        raise ValueError("steps and commands cannot both be non-empty")
    if verify_steps and verify_commands:
        raise ValueError("verify_steps and verify_commands cannot both be non-empty")

    primary: list[tuple[str, str]] = []
    if steps:
        primary = [(str(item["name"]), str(item["command"])) for item in steps]
    else:
        primary = [(f"command-{index}", str(command)) for index, command in enumerate(commands, 1)]

    verification: list[tuple[str, str]] = []
    if verify_steps:
        verification = [
            (str(item["name"]), str(item["command"])) for item in verify_steps
        ]
    else:
        verification = [
            (f"verification-{index}", str(command))
            for index, command in enumerate(verify_commands, 1)
        ]

    total = len(primary) + len(verification)
    plan: list[dict[str, Any]] = []
    stage_index = 1
    for phase, entries in (("commands", primary), ("verification", verification)):
        for name, command in entries:
            plan.append(
                {
                    "stage_name": name,
                    "stage_index": stage_index,
                    "stage_total": total,
                    "stage_phase": phase,
                    "command": command,
                }
            )
            stage_index += 1
    return plan


def run_command_list(
    commands: list[str],
    timeout: int,
    previous: dict[str, dict[str, Any]] | None = None,
    stages: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    history = {} if previous is None else dict(previous)
    results: list[dict[str, Any]] = []

    for offset, command in enumerate(commands):
        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"invalid command: {command!r}")
        stage = stages[offset] if stages is not None else None

        if command in history:
            reused = dict(history[command])
            reused["reused"] = True
            if stage is not None:
                reused.update(stage)
            log(f"command reuse: {command}")
            results.append(reused)
            if reused["exit_code"] != 0:
                break
            continue

        result = run_command(command, timeout, stage=stage)
        if stage is not None:
            result.update(stage)
        history[command] = result
        results.append(result)
        if result["exit_code"] != 0:
            break

    return results, history


def git_snapshot() -> tuple[dict[str, Any], dict[str, Any]]:
    status = process(["git", "status", "--short"], WORK)
    diff = process(["git", "diff", "--no-ext-diff"], WORK)
    return status, diff


def process_task(task: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task["id"])
    mode = str(task.get("mode", "commands"))
    if mode != "commands":
        raise ValueError(
            f"unsupported mode {mode!r}; this daemon executes deterministic commands only"
        )

    branch = str(task.get("work_branch", "main"))
    allow_write = bool(task.get("allow_write", False))
    patch = task.get("patch")
    writes = task.get("writes", [])
    deletes = task.get("deletes", [])
    commands = task.get("commands", [])
    verify_commands = task.get("verify_commands", [])
    steps = task.get("steps", [])
    verify_steps = task.get("verify_steps", [])

    if patch is not None and not isinstance(patch, str):
        raise ValueError("patch must be a string")
    if not isinstance(writes, list):
        raise ValueError("writes must be a list")
    if not isinstance(deletes, list):
        raise ValueError("deletes must be a list")
    if not isinstance(commands, list):
        raise ValueError("commands must be a list")
    if not isinstance(verify_commands, list):
        raise ValueError("verify_commands must be a list")
    if not isinstance(steps, list):
        raise ValueError("steps must be a list")
    if not isinstance(verify_steps, list):
        raise ValueError("verify_steps must be a list")

    stage_plan = stage_plan_for(task)
    primary_stages = [stage for stage in stage_plan if stage["stage_phase"] == "commands"]
    verification_stages = [
        stage for stage in stage_plan if stage["stage_phase"] == "verification"
    ]

    requested_edit = bool((patch and patch.strip()) or writes or deletes)
    if requested_edit and not allow_write:
        raise ValueError("task requests edits but allow_write is false")

    timeout = command_timeout_for(task)
    started_at = now_iso()
    log(
        f"starting task {task_id} branch={branch} "
        f"mode=commands write={allow_write} timeout={timeout}s"
    )

    prepare_work(branch, task_id=task_id)

    result: dict[str, Any] = {
        "id": task_id,
        "status": "failed",
        "mode": "commands",
        "work_branch": branch,
        "allow_write": allow_write,
        "started_at": started_at,
        "command_timeout": timeout,
        "edits": {},
        "commands": [],
        "verification": [],
        "stages": [],
    }

    command_history: dict[str, dict[str, Any]] = {}
    failure_reason: str | None = None

    try:
        if patch and patch.strip():
            patch_result = apply_patch(patch)
            result["edits"]["patch"] = patch_result
            if not patch_result.get("applied"):
                failure_reason = "patch_failed"

        if failure_reason is None and writes:
            result["edits"]["writes"] = apply_writes(writes)

        if failure_reason is None and deletes:
            result["edits"]["deletes"] = apply_deletes(
                [str(item) for item in deletes]
            )

        if failure_reason is None and commands:
            command_results, command_history = run_command_list(
                [str(item) for item in commands],
                timeout,
                command_history,
                primary_stages,
            )
            result["commands"] = command_results
            if command_results and command_results[-1]["exit_code"] != 0:
                failure_reason = "command_failed"

        if failure_reason is None and steps:
            command_results, command_history = run_command_list(
                [str(item["command"]) for item in steps],
                timeout,
                command_history,
                primary_stages,
            )
            result["commands"] = command_results
            if command_results and command_results[-1]["exit_code"] != 0:
                failure_reason = "command_failed"

        if failure_reason is None and verify_commands:
            verification_results, command_history = run_command_list(
                [str(item) for item in verify_commands],
                timeout,
                command_history,
                verification_stages,
            )
            result["verification"] = verification_results
            if verification_results and verification_results[-1]["exit_code"] != 0:
                failure_reason = "verification_failed"

        if failure_reason is None and verify_steps:
            verification_results, command_history = run_command_list(
                [str(item["command"]) for item in verify_steps],
                timeout,
                command_history,
                verification_stages,
            )
            result["verification"] = verification_results
            if verification_results and verification_results[-1]["exit_code"] != 0:
                failure_reason = "verification_failed"

        executed = result["commands"] + result["verification"]
        result["stages"] = [
            {
                "stage_name": item.get("stage_name"),
                "stage_index": item.get("stage_index"),
                "stage_total": item.get("stage_total"),
                "stage_phase": item.get("stage_phase"),
                "outcome": "reused" if item.get("reused") else (
                    "passed" if item.get("exit_code") == 0 else "failed"
                ),
                "elapsed_seconds": item.get("elapsed_seconds"),
            }
            for item in executed
        ]

        status, diff = git_snapshot()
        result["git_status"] = status
        result["git_diff"] = diff

        if status["exit_code"] != 0 or diff["exit_code"] != 0:
            failure_reason = failure_reason or "git_snapshot_failed"

        dirty = bool(status.get("output", "").strip())
        if not allow_write and dirty:
            failure_reason = failure_reason or "unexpected_worktree_changes"

        if requested_edit and not dirty:
            failure_reason = failure_reason or "requested_edit_produced_no_diff"

        if failure_reason is None:
            result["status"] = "done"
        else:
            result["failure_reason"] = failure_reason

        result["finished_at"] = now_iso()
        return result

    except Exception as exc:
        result["status"] = "failed"
        result["failure_reason"] = "exception"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        try:
            status, diff = git_snapshot()
            result["git_status"] = status
            result["git_diff"] = diff
        except Exception:
            pass
        result["finished_at"] = now_iso()
        return result
    finally:
        checkpoint_ok = True
        try:
            checkpoint = checkpoint_worktree(task_id, reason="task-exit")
            if checkpoint is not None:
                result["workspace_checkpoint"] = checkpoint
        except Exception as exc:
            checkpoint_ok = False
            result["status"] = "failed"
            result["failure_reason"] = "workspace_checkpoint_failed"
            result["checkpoint_error"] = f"{type(exc).__name__}: {exc}"
            log(
                "workspace checkpoint failed; cleanup skipped to preserve dirty state: "
                f"{type(exc).__name__}: {exc}"
            )
        if checkpoint_ok:
            cleanup_work()


def publish_result(task_id: str, result: dict[str, Any]) -> None:
    results_dir = CONTROL / ".agent" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{task_id}.json"
    path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    relative = str(path.relative_to(CONTROL))
    add = process(["git", "add", "--", relative], CONTROL)
    if add["exit_code"] != 0:
        raise RuntimeError(add["output"])

    commit = process(
        ["git", "commit", "-m", f"Agent result: {task_id}"],
        CONTROL,
    )
    if commit["exit_code"] != 0:
        status = process(["git", "status", "--short", "--", relative], CONTROL)
        if status["exit_code"] != 0 or status["output"].strip():
            raise RuntimeError(commit["output"])

    pull = process(
        ["git", "pull", "--rebase", "origin", CONTROL_BRANCH],
        CONTROL,
        timeout=180,
    )
    if pull["exit_code"] != 0:
        raise RuntimeError(pull["output"])

    push = process(
        ["git", "push", "origin", CONTROL_BRANCH],
        CONTROL,
        timeout=180,
    )
    if push["exit_code"] != 0:
        raise RuntimeError(push["output"])

    log(f"published result {task_id}")
