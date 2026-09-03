#!/usr/bin/env python3
"""Persistent local operator state for emergency Local Agent controls."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_process import atomic_write_text, fsync_directory
from agent_repository import default_registry_path, load_repository_registry

STATE_DIR = Path.home() / "Library" / "Application Support" / "local-agent"
DISABLED_PATH = STATE_DIR / "disabled.json"
_RUNTIME_DIR_NAMES = ("claims", "corrupt-claims", "runs", "result-spool")
_GLOBAL_RUNTIME_FILES = ("status.json",)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def disabled_state() -> dict[str, Any]:
    try:
        payload = json.loads(DISABLED_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def is_disabled() -> bool:
    # Marker presence is intentionally fail-closed, even when its JSON is damaged.
    return DISABLED_PATH.is_file()


def disable_agent(
    *,
    control_id: str | None = None,
    repository_id: str | None = None,
    reason: str = "operator_request",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": 1,
        "disabled": True,
        "disabled_at": now_iso(),
        "reason": reason,
    }
    if control_id:
        payload["control_id"] = control_id
    if repository_id:
        payload["repository_id"] = repository_id
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        DISABLED_PATH,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    )
    return payload


def enable_agent() -> bool:
    try:
        DISABLED_PATH.unlink()
    except FileNotFoundError:
        return False
    fsync_directory(DISABLED_PATH.parent)
    return True


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _reset_directory(path: Path) -> int:
    files = 0
    if path.exists():
        files = sum(1 for item in path.rglob("*") if item.is_file() or item.is_symlink())
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return files


def _remove_file(path: Path) -> int:
    try:
        path.unlink()
    except FileNotFoundError:
        return 0
    return 1


def reset_runtime_state(*, registry_path: Path | None = None) -> dict[str, Any]:
    """Destructively clear local ephemeral runtime only while admission is disabled."""
    if not is_disabled():
        raise RuntimeError("runtime reset requires Local Agent to be disabled first")

    resolved_registry = registry_path or default_registry_path(Path.home())
    repositories = load_repository_registry(path=resolved_registry)
    removed_files = 0
    repository_ids: list[str] = []

    for repository in repositories:
        repository_ids.append(repository.repository_id)
        state_root = STATE_DIR / "repositories" / repository.repository_id
        for name in _RUNTIME_DIR_NAMES:
            removed_files += _reset_directory(state_root / name)
        removed_files += _remove_file(state_root / "status.json")

    # Also clear legacy single-repository runtime so an old install cannot recover
    # stale claims after a multi-repository hard reset.
    for name in _RUNTIME_DIR_NAMES:
        removed_files += _reset_directory(STATE_DIR / name)

    # Global supervisor status is ephemeral too. Keeping it after a destructive
    # reset can make agentctl report a dead pre-reset PID/version as if it were
    # the current daemon, which is operationally misleading during rollout.
    for name in _GLOBAL_RUNTIME_FILES:
        removed_files += _remove_file(STATE_DIR / name)

    return {
        "reset": True,
        "repository_ids": repository_ids,
        "removed_files": removed_files,
        "registry": str(resolved_registry),
        "disabled": True,
    }


def command_status(_args: argparse.Namespace) -> int:
    state = disabled_state()
    _print_json(
        {
            "disabled": is_disabled(),
            "state": state or None,
            "marker": str(DISABLED_PATH),
        }
    )
    return 0


def command_disable(args: argparse.Namespace) -> int:
    state = disable_agent(reason=args.reason)
    _print_json({"disabled": True, "state": state, "marker": str(DISABLED_PATH)})
    return 0


def command_enable(_args: argparse.Namespace) -> int:
    changed = enable_agent()
    _print_json(
        {
            "disabled": False,
            "changed": changed,
            "marker": str(DISABLED_PATH),
        }
    )
    return 0


def command_reset_runtime(args: argparse.Namespace) -> int:
    try:
        payload = reset_runtime_state(registry_path=args.registry)
    except Exception as exc:
        _print_json(
            {
                "reset": False,
                "error": f"{type(exc).__name__}: {exc}",
                "disabled": is_disabled(),
            }
        )
        return 2
    _print_json(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Emergency Local Agent operator controls"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="show persistent disable state")
    status.set_defaults(func=command_status)

    disable = sub.add_parser("disable", help="persistently stop task admission")
    disable.add_argument("--reason", default="operator_cli")
    disable.set_defaults(func=command_disable)

    enable = sub.add_parser("enable", help="clear persistent disable state")
    enable.set_defaults(func=command_enable)

    reset_runtime = sub.add_parser(
        "reset-runtime",
        help="clear local claims, result spool, and run state while disabled",
    )
    reset_runtime.add_argument("--registry", type=Path)
    reset_runtime.set_defaults(func=command_reset_runtime)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
