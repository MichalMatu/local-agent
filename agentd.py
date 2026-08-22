#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import agent_core as core

HOME = Path.home()
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

core.COMMAND_TIMEOUT = COMMAND_TIMEOUT
core.MAX_COMMAND_TIMEOUT = MAX_COMMAND_TIMEOUT

_last_self_update_check = 0.0
_daemon_lock_handle: Any | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    core.log(message)


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
    tasks_dir = core.CONTROL / ".agent" / "tasks"
    results_dir = core.CONTROL / ".agent" / "results"
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

        if (results_dir / f"{task_id}.json").exists():
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
        "started_at": claim.get("started_at"),
        "finished_at": now_iso(),
        "error": (
            "Previous daemon instance ended while this task was claimed. "
            "Automatic replay was blocked."
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
            log(f"invalid stale claim {path.name}: {exc}")
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
    unstaged = _git(["git", "diff", "--quiet"])
    staged = _git(["git", "diff", "--cached", "--quiet"])
    return unstaged.returncode == 0 and staged.returncode == 0


def _read_rejected_update() -> dict[str, Any]:
    try:
        return json.loads(REJECTED_UPDATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _remember_rejected_update(remote_sha: str) -> None:
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


def _validate_installed_update() -> tuple[bool, str]:
    commands = [
        [sys.executable, "-m", "py_compile", "agentd.py", "agent_core.py"],
    ]
    if (SELF_REPO / "test_agentd.py").exists():
        commands.append([sys.executable, "-m", "unittest", "-q", "test_agentd.py"])

    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=SELF_REPO,
                env=core.ENV,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"{command!r}: {exc}"
        if result.returncode != 0:
            return False, result.stdout.strip()
    return True, ""


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
        log("self-update skipped: unable to resolve local/remote revision")
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
        log(
            "self-update skipped: local-agent main is not a fast-forward "
            f"of origin/{SELF_BRANCH}"
        )
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
        log(
            "self-update validation failed; rolling back: "
            + core.bounded(error, 2000)
        )
        rollback = _git(["git", "reset", "--hard", local_sha], timeout=60)
        if rollback.returncode != 0:
            log("CRITICAL: self-update rollback failed")
        else:
            _remember_rejected_update(remote_sha)
        return False

    REJECTED_UPDATE_PATH.unlink(missing_ok=True)
    log(f"self-update installed {remote_sha[:9]}; restarting daemon")
    try:
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])
    except OSError as exc:
        log(f"self-update exec failed; asking launchd to restart: {exc}")
        raise SystemExit(75) from exc


def main() -> None:
    global _daemon_lock_handle

    _daemon_lock_handle = acquire_daemon_lock()
    log(
        "Local Agent daemon v3 starting; "
        f"mode=deterministic command_timeout={COMMAND_TIMEOUT}s "
        f"self_update={SELF_UPDATE_INTERVAL}s"
    )

    while True:
        try:
            recover_stale_claims()
            core.sync_control()
            maybe_self_update()

            tasks = pending_tasks()
            if not tasks:
                log("no pending tasks")

            for _, task in tasks:
                task_id = str(task.get("id", "unknown"))
                if not claim_task(task_id):
                    continue

                try:
                    result = core.process_task(task)
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
                    core.publish_result(task_id, result)
                except Exception as exc:
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
