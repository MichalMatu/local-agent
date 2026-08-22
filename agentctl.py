#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import agent_core as core
import agentd


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def command_status(_args: argparse.Namespace) -> int:
    payload = read_json(agentd.LOCAL_STATUS_PATH)
    if payload is None:
        print_json({"state": "unknown", "error": "status file not found"})
        return 1
    print_json(payload)
    return 0


def command_task(args: argparse.Namespace) -> int:
    path = agentd.LOCAL_RUNS_DIR / f"{args.task_id}.json"
    payload = read_json(path)
    if payload is None:
        print_json({"task_id": args.task_id, "state": "unknown"})
        return 1
    print_json(payload)
    return 0


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
        agentd.validate_task(task)
    except Exception as exc:
        print_json({"valid": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1
    print_json(
        {
            "valid": True,
            "id": task["id"],
            "task_digest": agentd.task_digest(task),
            "command_timeout": int(task.get("command_timeout", core.COMMAND_TIMEOUT)),
            "idle_timeout": int(task.get("idle_timeout", 600)),
            "task_timeout": int(task.get("task_timeout", 3600)),
        }
    )
    return 0


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def command_doctor(_args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []
    checks.append(_check("self_repo", (agentd.SELF_REPO / ".git").exists(), str(agentd.SELF_REPO)))
    checks.append(_check("control_repo", (core.CONTROL / ".git").exists(), str(core.CONTROL)))
    checks.append(_check("work_repo", (core.WORK / ".git").exists(), str(core.WORK)))
    checks.append(_check("status_file", agentd.LOCAL_STATUS_PATH.exists(), str(agentd.LOCAL_STATUS_PATH)))

    try:
        proc = subprocess.run(
            ["pgrep", "-f", str((agentd.SELF_REPO / "agentd.py").resolve())],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
        pids = [line for line in proc.stdout.splitlines() if line.strip()]
        checks.append(_check("single_daemon", len(pids) == 1, f"pids={pids}"))
    except Exception as exc:
        checks.append(_check("single_daemon", False, str(exc)))

    ok = all(item["ok"] for item in checks)
    print_json({"ok": ok, "daemon_version": agentd.DAEMON_VERSION, "checks": checks})
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Agent control and diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="show local daemon status")
    status.set_defaults(func=command_status)

    task = sub.add_parser("task", help="show local task progress")
    task.add_argument("task_id")
    task.set_defaults(func=command_task)

    validate = sub.add_parser("validate-task", help="validate a task JSON file")
    validate.add_argument("path")
    validate.set_defaults(func=command_validate)

    doctor = sub.add_parser("doctor", help="run daemon installation checks")
    doctor.set_defaults(func=command_doctor)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
