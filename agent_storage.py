#!/usr/bin/env python3
"""Storage policy for local-agent repository workspaces."""
from __future__ import annotations

from pathlib import Path
from typing import Any

CONTROL_HISTORY_DEPTH = 256
CONTROL_HISTORY_WARNING_COMMITS = CONTROL_HISTORY_DEPTH * 2
CONTROL_HISTORY_WARNING_BYTES = 64 * 1024**2
CONTROL_WORKTREE_WARNING_BYTES = 256 * 1024**2
WORKTREE_WARNING_BYTES = 2 * 1024**3
DIAGNOSTIC_FILE_LIMIT = 100_000
CONTROL_SPARSE_PATHS = (".agent",)


def bounded_control_pull_args(branch: str) -> list[str]:
    """Git arguments that keep an already-shallow control checkout bounded."""
    return [
        "pull",
        "--rebase",
        "--depth",
        str(CONTROL_HISTORY_DEPTH),
        "--no-tags",
        "origin",
        branch,
    ]


def sync_control(core_module: Any) -> None:
    """Synchronize the active control checkout while preserving its shallow boundary."""
    with core_module.CONTROL_GIT_LOCK:
        result = core_module.process(
            ["git", "checkout", core_module.CONTROL_BRANCH],
            core_module.CONTROL,
        )
        if result["exit_code"] != 0:
            raise RuntimeError(result["output"])

        result = core_module.process(
            ["git", *bounded_control_pull_args(core_module.CONTROL_BRANCH)],
            core_module.CONTROL,
        )
        if result["exit_code"] != 0:
            raise RuntimeError(result["output"])


def git_bool(core_module: Any, path: Path, args: list[str]) -> bool | None:
    """Read a Git boolean-like diagnostic without raising on unsupported settings."""
    result = core_module.process(
        ["git", *args],
        path,
        timeout=30,
        log_commands=False,
    )
    if result["exit_code"] != 0:
        return None
    value = str(result.get("output", "")).strip().lower()
    if value in {"true", "yes", "on", "1"}:
        return True
    if value in {"false", "no", "off", "0"}:
        return False
    return None
