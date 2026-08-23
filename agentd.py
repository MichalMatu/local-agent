#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import agent_core as core
from agent_runtime import (
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_TASK_TIMEOUT,
    RuntimeExecutor,
    task_digest,
    validate_task,
)

DAEMON_VERSION = "4.4.0"
HOME = Path.home()
SELF_REPO = Path(__file__).resolve().parent
SELF_BRANCH = "main"
SELF_UPDATE_INTERVAL = 60
POLL_SECONDS = 15
REMOTE_HEARTBEAT_SECONDS = 300
RUN_PROGRESS_SECONDS = 60
RUN_HEARTBEAT_SECONDS = 60

STATE_DIR = HOME / "Library" / "Application Support" / "local-agent"
CLAIMS_DIR = STATE_DIR / "claims"
CORRUPT_CLAIMS_DIR = STATE_DIR / "corrupt-claims"
DAEMON_LOCK_PATH = STATE_DIR / "agentd.lock"
REJECTED_UPDATE_PATH = STATE_DIR / "rejected-self-update.json"
LOCAL_STATUS_PATH = STATE_DIR / "status.json"
LOCAL_RUNS_DIR = STATE_DIR / "runs"

REMOTE_DAEMON_STATUS = ".agent/status/daemon.json"
REMOTE_CONTROL_REQUEST = ".agent/daemon/control.json"
REMOTE_CONTROL_ACK_DIR = ".agent/daemon/acks"
REMOTE_RUNS_DIR = ".agent/runs"

core.COMMAND_TIMEOUT = 900
core.MAX_COMMAND_TIMEOUT = 1500
runtime = RuntimeExecutor(core)

_last_self_update_check = 0.0
_last_remote_status = 0.0
_last_status_state: str | None = None
_daemon_lock_handle: Any | None = None
_current_task_id: str | None = None
_current_attempt_id: str | None = None
_current_task_digest: str | None = None
_current_progress: dict[str, Any] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    core.log(message)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def publish_control_json(
    relative: str,
    payload: dict[str, Any],
    *,
    commit_message: str,
) -> bool:
    target = (core.CONTROL / relative).resolve()
    root = core.CONTROL.resolve()
    if root not in target.parents:
        raise ValueError(f"control path escapes repository: {relative!r}")

    atomic_write_json(target, payload)
    add = core.process(["git", "add", "--", relative], core.CONTROL)
    if add["exit_code"] != 0:
        raise RuntimeError(add["output"])

    staged = core.process(
        ["git", "diff", "--cached", "--quiet", "--", relative],
        core.CONTROL,
    )
    if staged["exit_code"] == 0:
        return False
    if staged["exit_code"] != 1:
        raise RuntimeError(staged["output"])

    commit = core.process(
        ["git", "commit", "-m", commit_message, "--", relative],
        core.CONTROL,
    )
    if commit["exit_code"] != 0:
        raise RuntimeError(commit["output"])

    for attempt in range(2):
        pull = core.process(
            ["git", "pull", "--rebase", "origin", core.CONTROL_BRANCH],
            core.CONTROL,
            timeout=180,
        )
        if pull["exit_code"] != 0:
            raise RuntimeError(pull["output"])
        push = core.process(
            ["git", "push", "origin", core.CONTROL_BRANCH],
            core.CONTROL,
            timeout=180,
        )
        if push["exit_code"] == 0:
            return True
        if attempt == 1:
            raise RuntimeError(push["output"])
    return False


def self_revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=SELF_REPO,
            env=core.ENV,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def daemon_status_payload(state: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": 1,
        "daemon_version": DAEMON_VERSION,
        "state": state,
        "pid": os.getpid(),
        "updated_at": now_iso(),
        "self_revision": self_revision(),
        "poll_seconds": POLL_SECONDS,
        "self_update_seconds": SELF_UPDATE_INTERVAL,
        "command_timeout_default": core.COMMAND_TIMEOUT,
        "idle_timeout_default": DEFAULT_IDLE_TIMEOUT,
        "task_timeout_default": DEFAULT_TASK_TIMEOUT,
        "current_task_id": _current_task_id,
        "current_attempt_id": _current_attempt_id,
        "current_task_digest": _current_task_digest,
    }
    payload.update(extra)
    return payload


def publish_daemon_status(
    state: str,
    *,
    force_remote: bool = False,
    **extra: Any,
) -> None:
    global _last_remote_status, _last_status_state

    payload = daemon_status_payload(state, **extra)
    atomic_write_json(LOCAL_STATUS_PATH, payload)
    now = time.monotonic()
    should_publish = (
        force_remote
        or state != _last_status_state
        or now - _last_remote_status >= REMOTE_HEARTBEAT_SECONDS
    )
    _last_status_state = state
    if not should_publish:
        return
    try:
        publish_control_json(
            REMOTE_DAEMON_STATUS,
            payload,
            commit_message=f"Agent daemon status: {state}",
        )
        _last_remote_status = now
    except Exception as exc:
        log(f"remote daemon status publish failed: {type(exc).__name__}: {exc}")


def task_claim_path(task_id: str) -> Path:
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    return CLAIMS_DIR / f"{digest}.json"


def claim_task(task: dict[str, Any]) -> dict[str, Any] | None:
    validate_task(task)
    task_id = str(task["id"])
    digest = task_digest(task)
    attempt_id = secrets.token_hex(12)
    payload = {
        "id": task_id,
        "task_digest": digest,
        "attempt_id": attempt_id,
        "pid": os.getpid(),
        "daemon_version": DAEMON_VERSION,
        "started_at": now_iso(),
    }
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    path = task_claim_path(task_id)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        if existing.get("task_digest") not in (None, digest):
            log(f"task id payload mismatch; refusing execution: {task_id}")
        else:
            log(f"task already claimed; refusing replay: {task_id}")
        return None

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    log(f"claimed task {task_id} attempt={attempt_id}")
    return payload


def release_task_claim(task_id: str) -> None:
    try:
        task_claim_path(task_id).unlink()
        log(f"released task claim {task_id}")
    except FileNotFoundError:
        pass


def invalid_task_result(task_id: str, error: Exception) -> dict[str, Any]:
    return {
        "id": task_id,
        "status": "failed",
        "failure_reason": "invalid_task_file",
        "started_at": None,
        "finished_at": now_iso(),
        "daemon_version": DAEMON_VERSION,
        "error": f"{type(error).__name__}: {error}",
    }


def recover_invalid_task_files() -> None:
    tasks_dir = core.CONTROL / ".agent" / "tasks"
    results_dir = core.CONTROL / ".agent" / "results"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(tasks_dir.glob("*.json")):
        # A malformed file cannot reliably provide task.id, so its filename stem is
        # the durable rejection key. Valid historical task files are allowed to use
        # a filename alias/prefix that differs from task.id.
        rejection_id = path.stem
        rejection_result = results_dir / f"{rejection_id}.json"
        if rejection_result.exists():
            continue
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
            validate_task(task)
        except Exception as exc:
            log(f"rejecting invalid task file {path.name}: {type(exc).__name__}: {exc}")
            result = invalid_task_result(rejection_id, exc)
            try:
                core.publish_result(rejection_id, result)
            except Exception as publish_exc:
                log(f"failed to publish invalid-task result for {rejection_id}: {publish_exc}")
                continue
            publish_run_state(
                rejection_id,
                {
                    "event": "invalid_task_rejected",
                    "status": "failed",
                    "failure_reason": "invalid_task_file",
                    "updated_at": now_iso(),
                },
                force_remote=True,
            )


def pending_tasks() -> list[tuple[Path, dict[str, Any]]]:
    tasks_dir = core.CONTROL / ".agent" / "tasks"
    results_dir = core.CONTROL / ".agent" / "results"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    pending: list[tuple[Path, dict[str, Any]]] = []

    for path in sorted(tasks_dir.glob("*.json")):
        # First skip a terminal malformed-file rejection keyed by filename.
        task_id_hint = path.stem
        if (results_dir / f"{task_id_hint}.json").exists():
            continue
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
            validate_task(task)
            task_id = str(task["id"])
        except Exception as exc:
            log(f"invalid task file {path.name}: {type(exc).__name__}: {exc}")
            continue

        # Valid historical files may use a filename prefix/alias. Results and claims
        # are keyed by the immutable payload id, not by the queue filename.
        result_path = results_dir / f"{task_id}.json"
        if result_path.exists():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except Exception:
                result = {}
            old_digest = result.get("task_digest")
            new_digest = task_digest(task)
            if old_digest and old_digest != new_digest:
                log(f"task id reuse detected after result; refusing: {task_id}")
            continue
        if task_claim_path(task_id).exists():
            log(f"task already claimed; skipping replay: {task_id}")
            continue
        pending.append((path, task))
    return pending


def interrupted_result(task_id: str, claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task_id,
        "status": "failed",
        "failure_reason": "interrupted_previous_attempt",
        "task_digest": claim.get("task_digest"),
        "attempt_id": claim.get("attempt_id"),
        "daemon_version": claim.get("daemon_version"),
        "started_at": claim.get("started_at"),
        "finished_at": now_iso(),
        "error": (
            "Previous daemon instance ended while this task was claimed. "
            "Automatic replay was blocked."
        ),
    }


def _task_for_claim_path(path: Path) -> dict[str, Any] | None:
    tasks_dir = core.CONTROL / ".agent" / "tasks"
    for task_path in sorted(tasks_dir.glob("*.json")):
        try:
            task = json.loads(task_path.read_text(encoding="utf-8"))
            validate_task(task)
            task_id = str(task["id"])
        except Exception:
            continue
        if task_claim_path(task_id).name == path.name:
            return task
    return None


def _quarantine_corrupt_claim(path: Path) -> Path:
    CORRUPT_CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    target = CORRUPT_CLAIMS_DIR / f"{path.stem}.{time.time_ns()}.json"
    os.replace(path, target)
    return target


def corrupt_claim_result(task: dict[str, Any], error: Exception) -> dict[str, Any]:
    task_id = str(task["id"])
    return {
        "id": task_id,
        "status": "failed",
        "failure_reason": "corrupt_claim_state",
        "task_digest": task_digest(task),
        "attempt_id": None,
        "daemon_version": DAEMON_VERSION,
        "started_at": None,
        "finished_at": now_iso(),
        "error": (
            f"Durable claim state could not be decoded ({type(error).__name__}: {error}). "
            "Automatic replay was blocked and the corrupt claim was quarantined."
        ),
    }


def recover_stale_claims() -> None:
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    results_dir = core.CONTROL / ".agent" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(CLAIMS_DIR.glob("*.json")):
        try:
            claim = json.loads(path.read_text(encoding="utf-8"))
            task_id = str(claim["id"])
        except Exception as exc:
            task = _task_for_claim_path(path)
            if task is None:
                quarantined = _quarantine_corrupt_claim(path)
                log(
                    f"quarantined unmatched corrupt claim {path.name} -> "
                    f"{quarantined.name}: {type(exc).__name__}: {exc}"
                )
                continue

            task_id = str(task["id"])
            result = corrupt_claim_result(task, exc)
            log(f"recovering corrupt claim without replay: {task_id}")
            try:
                core.publish_result(task_id, result)
            except Exception as publish_exc:
                log(f"failed to publish corrupt-claim result for {task_id}: {publish_exc}")
                continue
            publish_run_state(
                task_id,
                {
                    "event": "recovered_corrupt_claim",
                    "status": "failed",
                    "failure_reason": "corrupt_claim_state",
                    "attempt_id": None,
                    "task_digest": result.get("task_digest"),
                    "updated_at": now_iso(),
                },
                force_remote=True,
            )
            quarantined = _quarantine_corrupt_claim(path)
            log(f"quarantined corrupt claim for {task_id}: {quarantined.name}")
            continue

        result_path = results_dir / f"{task_id}.json"
        if result_path.exists():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except Exception:
                result = interrupted_result(task_id, claim)
        else:
            result = interrupted_result(task_id, claim)

        log(f"recovering interrupted task without replay: {task_id}")
        try:
            core.publish_result(task_id, result)
        except Exception as exc:
            log(f"failed to publish interrupted result for {task_id}: {exc}")
            continue
        publish_run_state(
            task_id,
            {
                "event": "recovered_interrupted_attempt",
                "status": "failed",
                "failure_reason": result.get("failure_reason"),
                "attempt_id": claim.get("attempt_id"),
                "task_digest": claim.get("task_digest"),
                "updated_at": now_iso(),
            },
            force_remote=True,
        )
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


def _git(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=SELF_REPO,
        env=core.ENV,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def tracked_self_repo_clean() -> bool:
    try:
        status = _git(["git", "status", "--porcelain", "--untracked-files=normal"])
    except (OSError, subprocess.TimeoutExpired):
        return False
    return status.returncode == 0 and not status.stdout.strip()


def self_repo_on_main_branch() -> bool:
    try:
        branch = _git(["git", "symbolic-ref", "--quiet", "--short", "HEAD"])
    except (OSError, subprocess.TimeoutExpired):
        return False
    return branch.returncode == 0 and branch.stdout.strip() == SELF_BRANCH


def _read_rejected_update() -> dict[str, Any]:
    try:
        return json.loads(REJECTED_UPDATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _remember_rejected_update(remote_sha: str, error: str) -> None:
    atomic_write_json(
        REJECTED_UPDATE_PATH,
        {
            "sha": remote_sha,
            "rejected_at": now_iso(),
            "reason": "validation_failed",
            "error": core.bounded(error, 4000),
        },
    )


def _validate_installed_update() -> tuple[bool, str]:
    commands = [
        [
            sys.executable,
            "-m",
            "py_compile",
            "agentd.py",
            "agent_core.py",
            "agent_runtime.py",
            "agentctl.py",
        ],
        [sys.executable, "-m", "unittest", "discover", "-q"],
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=SELF_REPO,
                env=core.ENV,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"{command!r}: {exc}"
        if result.returncode != 0:
            return False, result.stdout.strip()
    return True, ""


def restart_self(reason: str) -> None:
    publish_daemon_status("restarting", force_remote=True, reason=reason)
    log(f"restarting daemon: {reason}")
    try:
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])
    except OSError as exc:
        log(f"exec restart failed; asking launchd to restart: {exc}")
        raise SystemExit(75) from exc


def maybe_self_update(force: bool = False) -> bool:
    global _last_self_update_check
    now = time.monotonic()
    if not force and now - _last_self_update_check < SELF_UPDATE_INTERVAL:
        return False
    _last_self_update_check = now
    if not (SELF_REPO / ".git").exists():
        return False
    if not self_repo_on_main_branch():
        log(f"self-update skipped: checkout is not on {SELF_BRANCH}")
        return False
    if not tracked_self_repo_clean():
        log("self-update skipped: checkout is not clean")
        return False

    try:
        fetch = _git(["git", "fetch", "--quiet", "origin", SELF_BRANCH])
    except (OSError, subprocess.TimeoutExpired) as exc:
        log(f"self-update fetch failed: {exc}")
        return False
    if fetch.returncode != 0:
        log(f"self-update fetch failed: {core.bounded(fetch.stdout.strip(), 2000)}")
        return False

    local = _git(["git", "rev-parse", "HEAD"])
    remote = _git(["git", "rev-parse", f"origin/{SELF_BRANCH}"])
    if local.returncode != 0 or remote.returncode != 0:
        return False
    local_sha = local.stdout.strip()
    remote_sha = remote.stdout.strip()
    if local_sha == remote_sha:
        REJECTED_UPDATE_PATH.unlink(missing_ok=True)
        return False
    if _read_rejected_update().get("sha") == remote_sha:
        return False

    ancestor = _git(["git", "merge-base", "--is-ancestor", local_sha, remote_sha])
    if ancestor.returncode != 0:
        log("self-update skipped: remote main is not a fast-forward")
        return False

    log(f"self-update available {local_sha[:9]} -> {remote_sha[:9]}")
    pull = _git(
        ["git", "pull", "--ff-only", "--quiet", "origin", SELF_BRANCH],
        timeout=120,
    )
    if pull.returncode != 0:
        log(f"self-update pull failed: {core.bounded(pull.stdout.strip(), 2000)}")
        return False

    valid, error = _validate_installed_update()
    if not valid:
        log("self-update validation failed; rolling back: " + core.bounded(error, 2000))
        rollback = _git(["git", "reset", "--hard", local_sha], timeout=60)
        if rollback.returncode == 0:
            _remember_rejected_update(remote_sha, error)
        else:
            log("CRITICAL: self-update rollback failed")
        return False

    REJECTED_UPDATE_PATH.unlink(missing_ok=True)
    log(f"self-update installed {remote_sha[:9]}")
    restart_self("self_update")
    return True


def _control_ack_path(control_id: str) -> Path:
    return core.CONTROL / REMOTE_CONTROL_ACK_DIR / f"{control_id}.json"


def publish_control_ack(
    control_id: str,
    action: str,
    status: str,
    **extra: Any,
) -> None:
    payload = {
        "id": control_id,
        "action": action,
        "status": status,
        "daemon_version": DAEMON_VERSION,
        "pid": os.getpid(),
        "updated_at": now_iso(),
    }
    payload.update(extra)
    publish_control_json(
        f"{REMOTE_CONTROL_ACK_DIR}/{control_id}.json",
        payload,
        commit_message=f"Agent daemon control ack: {control_id}",
    )


def handle_control_request() -> None:
    path = core.CONTROL / REMOTE_CONTROL_REQUEST
    if not path.exists():
        return
    try:
        request = json.loads(path.read_text(encoding="utf-8"))
        control_id = str(request["id"])
        action = str(request["action"])
    except Exception as exc:
        log(f"invalid daemon control request: {exc}")
        return
    if not control_id or len(control_id) > 120 or _control_ack_path(control_id).exists():
        return

    if action == "restart":
        publish_control_ack(control_id, action, "accepted")
        restart_self(f"remote_control:{control_id}")
    elif action == "self_update":
        publish_control_ack(control_id, action, "accepted")
        if not maybe_self_update(force=True):
            publish_control_ack(control_id, action, "completed", result="no_update")
    elif action == "status":
        publish_daemon_status("idle", force_remote=True)
        publish_control_ack(control_id, action, "completed")
    else:
        publish_control_ack(control_id, action, "rejected", error="unsupported_action")


def publish_run_state(
    task_id: str,
    payload: dict[str, Any],
    *,
    force_remote: bool,
) -> None:
    state = dict(payload)
    state.setdefault("task_id", task_id)
    state.setdefault("daemon_version", DAEMON_VERSION)
    state.setdefault("pid", os.getpid())
    state.setdefault("updated_at", now_iso())
    atomic_write_json(LOCAL_RUNS_DIR / f"{task_id}.json", state)
    if not force_remote:
        return
    try:
        publish_control_json(
            f"{REMOTE_RUNS_DIR}/{task_id}.json",
            state,
            commit_message=f"Agent progress: {task_id}",
        )
    except Exception as exc:
        log(f"remote run state publish failed for {task_id}: {exc}")


def make_progress_callback(task_id: str, attempt_id: str, digest: str):
    last_remote = 0.0
    last_remote_phase: str | None = None
    last_remote_stage: str | None = None

    def progress(event: dict[str, Any]) -> None:
        nonlocal last_remote, last_remote_phase, last_remote_stage
        global _current_progress
        enriched = dict(event)
        enriched.update(
            {
                "task_id": task_id,
                "attempt_id": attempt_id,
                "task_digest": digest,
                "daemon_version": DAEMON_VERSION,
                "daemon_pid": os.getpid(),
                "updated_at": now_iso(),
            }
        )
        _current_progress = enriched
        now = time.monotonic()
        event_name = str(event.get("event", ""))
        phase = str(event.get("stage_phase", event.get("phase", "")))
        stage_name = str(event.get("stage_name", ""))

        force_remote = event_name in {"task_started", "task_finished"}
        if event_name in {"command_started", "stage_progress"}:
            first_command = last_remote_phase is None
            phase_changed = bool(last_remote_phase) and phase != last_remote_phase
            stage_changed = bool(stage_name) and stage_name != last_remote_stage
            progress_due = now - last_remote >= RUN_PROGRESS_SECONDS
            force_remote = first_command or phase_changed or stage_changed or progress_due
        if event_name == "command_finished":
            if int(event.get("exit_code", 0)) != 0:
                force_remote = True
            elif float(event.get("elapsed_seconds", 0.0)) >= RUN_PROGRESS_SECONDS:
                force_remote = True
        if event_name == "command_heartbeat" and now - last_remote >= RUN_HEARTBEAT_SECONDS:
            force_remote = True

        publish_run_state(task_id, enriched, force_remote=force_remote)
        if force_remote:
            last_remote = now
            if phase:
                last_remote_phase = phase
            if stage_name:
                last_remote_stage = stage_name

        # Local status tracks every transition. Remote daemon status is health/state
        # telemetry, not a duplicate per-command stream. Detailed execution belongs
        # in .agent/runs/<task-id>.json.
        status_extra: dict[str, Any] = {"progress": enriched}
        if enriched.get("last_progress_at") is not None:
            status_extra["last_progress_at"] = enriched["last_progress_at"]
        if enriched.get("last_progress_message") is not None:
            status_extra["last_progress_message"] = enriched["last_progress_message"]
        publish_daemon_status("running", force_remote=force_remote, **status_extra)

    return progress


def shutdown_handler(signum: int, _frame: Any) -> None:
    log(f"received signal {signum}; terminating active command")
    runtime.terminate_active_command()
    raise SystemExit(128 + signum)


def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)


def execute_task(task: dict[str, Any]) -> None:
    global _current_task_id, _current_attempt_id, _current_task_digest, _current_progress
    claim = claim_task(task)
    if claim is None:
        return

    task_id = str(task["id"])
    _current_task_id = task_id
    _current_attempt_id = str(claim["attempt_id"])
    _current_task_digest = str(claim["task_digest"])
    _current_progress = {}
    progress = make_progress_callback(
        task_id,
        _current_attempt_id,
        _current_task_digest,
    )
    publish_daemon_status("running", force_remote=True)

    try:
        result = runtime.process_task(task, progress=progress)
    except Exception as exc:
        result = {
            "id": task_id,
            "status": "failed",
            "failure_reason": "daemon_exception",
            "task_digest": _current_task_digest,
            "started_at": claim.get("started_at"),
            "finished_at": now_iso(),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    result["attempt_id"] = _current_attempt_id
    result["daemon_version"] = DAEMON_VERSION
    result.setdefault("task_digest", _current_task_digest)

    try:
        core.publish_result(task_id, result)
    except Exception as exc:
        log(f"result publish failed for {task_id}: {exc}")
        publish_daemon_status(
            "result_publish_failed",
            force_remote=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    publish_run_state(
        task_id,
        {
            "event": "result_published",
            "status": result.get("status"),
            "failure_reason": result.get("failure_reason"),
            "attempt_id": _current_attempt_id,
            "task_digest": _current_task_digest,
            "finished_at": result.get("finished_at"),
            "updated_at": now_iso(),
        },
        force_remote=True,
    )
    release_task_claim(task_id)
    _current_task_id = None
    _current_attempt_id = None
    _current_task_digest = None
    _current_progress = {}
    publish_daemon_status("idle", force_remote=True)


def main() -> None:
    global _daemon_lock_handle
    _daemon_lock_handle = acquire_daemon_lock()
    install_signal_handlers()
    log(
        f"Local Agent daemon v{DAEMON_VERSION} starting; "
        f"command_timeout={core.COMMAND_TIMEOUT}s idle_timeout=600s "
        f"task_timeout=3600s self_update={SELF_UPDATE_INTERVAL}s"
    )

    core.sync_control()
    recover_stale_claims()
    recover_invalid_task_files()
    publish_daemon_status("idle", force_remote=True)

    while True:
        try:
            core.sync_control()
            recover_stale_claims()
            recover_invalid_task_files()
            handle_control_request()
            maybe_self_update()
            tasks = pending_tasks()
            if not tasks:
                log("no pending tasks")
                publish_daemon_status("idle")
            for _, task in tasks:
                execute_task(task)
        except SystemExit:
            raise
        except Exception as exc:
            log(f"poll loop error: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            publish_daemon_status(
                "error",
                force_remote=True,
                error=f"{type(exc).__name__}: {exc}",
            )
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
