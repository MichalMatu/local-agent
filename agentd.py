#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HOME = Path.home()
CONTROL = HOME / "agent-workspace" / "control"
WORK = HOME / "agent-workspace" / "work"
CONTROL_BRANCH = "agent-control"

SELF_REPO = Path(__file__).resolve().parent
SELF_BRANCH = "main"
SELF_UPDATE_INTERVAL = 60

STATE_DIR = HOME / "Library" / "Application Support" / "local-agent"
CLAIMS_DIR = STATE_DIR / "claims"
DAEMON_LOCK_PATH = STATE_DIR / "agentd.lock"
REJECTED_UPDATE_PATH = STATE_DIR / "rejected-self-update.json"

POLL_SECONDS = 15
COMMAND_TIMEOUT = 1200
MAX_COMMAND_TIMEOUT = 3600
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
_ACTIVE_PROCESS: subprocess.Popen[str] | None = None
_DAEMON_LOCK_HANDLE: Any | None = None
_last_self_update_check = 0.0


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
    log_command: bool = True,
) -> dict[str, Any]:
    if log_command:
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
        if log_command:
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


def _handle_shutdown(signum: int, _frame: Any) -> None:
    global _ACTIVE_PROCESS
    log(f"received signal {signum}; shutting down")
    if _ACTIVE_PROCESS is not None:
        kill_process_group(_ACTIVE_PROCESS)
    raise SystemExit(128 + signum)


def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)


def run_command(command: str, timeout: int) -> dict[str, Any]:
    global _ACTIVE_PROCESS

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
    _ACTIVE_PROCESS = proc

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

    try:
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
    finally:
        _ACTIVE_PROCESS = None

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


def prepare_work(branch: str) -> None:
    branch = validate_branch(branch)

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


def run_command_list(
    commands: list[str],
    timeout: int,
    previous: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    history = {} if previous is None else dict(previous)
    results: list[dict[str, Any]] = []

    for command in commands:
        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"invalid command: {command!r}")

        if command in history:
            reused = dict(history[command])
            reused["reused"] = True
            log(f"command reuse: {command}")
            results.append(reused)
            if reused["exit_code"] != 0:
                break
            continue

        result = run_command(command, timeout)
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

    requested_edit = bool((patch and patch.strip()) or writes or deletes)
    if requested_edit and not allow_write:
        raise ValueError("task requests edits but allow_write is false")

    timeout = command_timeout_for(task)
    started_at = now_iso()
    log(
        f"starting task {task_id} branch={branch} "
        f"mode=commands write={allow_write} timeout={timeout}s"
    )

    prepare_work(branch)

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
            )
            result["commands"] = command_results
            if command_results and command_results[-1]["exit_code"] != 0:
                failure_reason = "command_failed"

        if failure_reason is None and verify_commands:
            verification_results, command_history = run_command_list(
                [str(item) for item in verify_commands],
                timeout,
                command_history,
            )
            result["verification"] = verification_results
            if verification_results and verification_results[-1]["exit_code"] != 0:
                failure_reason = "verification_failed"

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


def task_claim_path(task_id: str) -> Path:
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    return CLAIMS_DIR / f"{digest}.json"


def claim_task(task_id: str) -> bool:
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    path = task_claim_path(task_id)
    payload = {
        "id": task_id,
        "pid": os.getpid(),
        "started_at": now_iso(),
    }

    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        log(f"task already claimed; refusing replay: {task_id}")
        return False

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

    log(f"claimed task {task_id}")
    return True


def release_task_claim(task_id: str) -> None:
    try:
        task_claim_path(task_id).unlink()
        log(f"released task claim {task_id}")
    except FileNotFoundError:
        pass


def pending_tasks() -> list[tuple[Path, dict[str, Any]]]:
    tasks_dir = CONTROL / ".agent" / "tasks"
    results_dir = CONTROL / ".agent" / "results"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    pending: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(tasks_dir.glob("*.json")):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
            task_id = str(task["id"])
        except Exception as exc:
            log(f"invalid task file {path.name}: {exc}")
            continue

        result_path = results_dir / f"{task_id}.json"
        if result_path.exists():
            continue
        if task_claim_path(task_id).exists():
            log(f"task already claimed; skipping replay: {task_id}")
            continue
        pending.append((path, task))
    return pendinY

def interrupted_result(task_id: str, claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task_id,
        "status": "failed",
        "failure_reason": "interrupted_previous_attempt",
        "started_at": claim.get("started_at"),
        "finished_at": now_iso(),
        "error": (
            "Previous daemon instance ended while this task was claimed. "
            "Automatic replay was blocked."
         ),
    }


def recover_stale_claims() -> None:
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    results_dir = CONTROL / ".agent" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(CLAIMS_DIR.glob("*.json")):
        try:
            claim = json.loads(path.read_text(encoding="utf-8"))
            task_id = str(claim["id"])
        except Exception as exc:
            log(f"invalid stale claim {path.name}: {exc}")
            continue

        result_path = results_dir / f"{task_id}.json"
        if result_path.exists():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except Exception as exc:
                log(f"invalid local result for {task_id}: {exc}")
                result = interrupted_result(task_id, claim)
        else:
            result = interrupted_result(task_id, claim)

        log(f"recovering interrupted task without replay: {task_id}")
        try:
            publish_result(task_id, result)
        except Exception as exc:
            log(f"failed to publish interrupted result for {task_id}: {exc}")
            continue

        release_task_claim(task_id)


def acquire_daemon_lock() -> Any:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    handle = DAEMON_LOCK_PATH.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another local-agent daemon is already running; exiting")
        raise SystemExit(0)

    handle.seek(0)
    handle.truncate()
    handle.write(json.dumps({"pid": os.getpid(), "started_at": now_iso()}) + "\n")
    handle.flush()
    os.fsync(handle.fileno())
    return handle


def _git_output(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=SELF_REPO,
        env=ENV,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def tracked_self_repo_clean() -> bool:
    unstaged = _git_output(["git", "diff", "--quiet"])
    staged = _git_output(["git", "diff", "--cached", "--quiet"])
    return unstaged.returncode == 0 and staged.returncode == 0


def maybe_self_update(force: bool = False) -> bool:
    global _last_self_update_check

    now = time.monotonic()
    if not force and now - _last_self_update_check < SELF_UPDATE_INTERVAL:
        return False
    _last_self_update_check = now

    if not (SELF_REPO / ".git").exists():
        return False
    if not tracked_self_repo_clean():
        log("self-update skipped: tracked local-agent changes are present")
        return False

    try:
        fetch = _git_output(["git", "fetch", "--quiet", "origin", SELF_BRANCH])
    except (OSError, subprocess.TimeoutExpired) as exc:
        log(f"self-update fetch failed: {exc}")
        return False
    if fetch.returncode != 0:
        log(f"self-update fetch failed: {bounded(fetch.stdout.strip(), 2000)}")
        return False

    local = _git_output(["git", "rev-parse", "HEAD"])
    remote = _git_output(["git", "rev-parse", f"origin/{SELF_BRANCH}"])
    if local.returncode != 0 or remote.returncode != 0:
        log("self-update skipped: unable to resolve local/remote revision")
        return False

    local_sha = local.stdout.strip()
    remote_sha = remote.stdout.strip()
    if local_sha == remote_sha:
        try:
            REJECTED_UPDATE_PATH.unlink()
        except FileNotFoundError:
            pass
        return False

    try:
        rejected = json.loads(REJECTED_UPDATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        rejected = {}
    if rejected.get("sha") == remote_sha:
        return False

    ancestor = _git_output(
        ["git", "merge-base", "--is-ancestor", local_sha, remote_sha]
    )
    if ancestor.returncode != 0:
        log(
            "self-update skipped: local-agent main is not a fast-forward "
            f"of origin/{SELF_BRANCH}"
        )
        return False

    log(f"self-update available {local_sha[:9]} -> {remote_sha[:9]}")
    pull = _git_output(
        ["git", "pull", "--ff-only", "--quiet", "origin", SELF_BRANCH],
        timeout=120,
    )
    if pull.returncode != 0:
        log(f"self-update pull failed: {bounded(pull.stdout.strip(), 2000)}")
        return False

    validation_commands = [
        [sys.executable, "-m", "py_compile", str(Path(__file__).resolve())],
    ]
    if (SELF_REPO / "test_agentd.py").exists():
        validation_commands.append(
            [sys.executable, "-m", "unittest", "-q", "test_agentd.py"]
        )

    validation_failure = ""
    for validation_command in validation_commands:
        try:
            validation = subprocess.run(
                validation_command,
                cwd=SELF_REPO,
                env=ENV,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            validation_failure = f"{validation_command!r}: {exc}"
            break
        if validation.returncode != 0:
            validation_failure = validation.stdout.strip()
            break

    if validation_failure:
        log(
            "self-update validation failed; rolling back: "
            + bounded(validation_failure, 2000)
        )
        rollback = _git_output(["git", "reset", "--hard", local_sha], timeout=60)
        if rollback.returncode != 0:
            log("CRITICAL: self-update rollback failed")
        else:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            REJECTED_UPDATE_PATH.write_text(
                json.dumps(
                    {
                        "sha": remote_sha,
                        "rejected_at": now_iso(),
                        "reason": "validation_failed",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return False

    try:
        REJECTED_UPDATE_PATH.unlink()
    except FileNotFoundError:
        pass

    log(f"self-update installed {remote_sha[:9]}; restarting daemon")
    try:
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])
    except OSError as exc:
        log(f"self-update exec failed; asking launchd to restart: {exc}")
        raise SystemExit(75) from exc
    return True


def main() -> None:
    global _DAEMON_LOCK_HANDLE

    install_signal_handlers()
    _DAEMON_LOCK_HANDLE = acquire_daemon_lock()

    log(
        "Local Agent daemon v3 starting; "
        f"mode=deterministic command_timeout={COMMAND_TIMEOUT}s "
        f"self_update={SELF_UPDATE_INTERVAL}s"
    )

    while True:
        try:
            # A stale claim is authoritative: recover/publish an interrupted
            # result instead of ever replaying the task automatically.
            recover_stale_claims()
            sync_control()

            # Self-update only happens between tasks, never while a command is
            # running. execv keeps launchd supervision and loads the new code.
            maybe_self_update()

            tasks = pending_tasks()
            if not tasks:
                log("no pending tasks")

            for _, task in tasks:
                task_id = str(task.get("id", "unknown"))
                if not claim_task(task_id):
                    continue

                try:
                    result = process_task(task)
                except Exception as exc:
                    result = {
                        "id": task_id,
                        "status": "failed",
                        "failure_reason": "daemon_exception",
                        "started_at": now_iso(),
                        "finished_at": now_iso(),
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                    }

                try:
                    publish_result(task_id, result)
                except Exception as exc:
                    # Keep the claim. The next poll will retry publication or
                    # publish an interrupted result, but it will not rerun the
                    # commands.
                    log(f"result publish failed for {task_id}: {exc}")
                    continue

                release_task_claim(task_id)

        except SystemExit:
            raise
        except Exception as exc:
            log(f"poll loop error: {type(exc).__name__}: {exc}")
            traceback.print_exc()

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
