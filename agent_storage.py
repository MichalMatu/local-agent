#!/usr/bin/env python3
"""Storage and resilient Git policy for local-agent repository workspaces."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

CONTROL_HISTORY_DEPTH = 256
CONTROL_HISTORY_WARNING_COMMITS = CONTROL_HISTORY_DEPTH * 2
CONTROL_HISTORY_WARNING_BYTES = 64 * 1024**2
CONTROL_WORKTREE_WARNING_BYTES = 256 * 1024**2
WORKTREE_WARNING_BYTES = 2 * 1024**3
DIAGNOSTIC_FILE_LIMIT = 100_000
CONTROL_SPARSE_PATHS = (".agent",)
GIT_NETWORK_RETRY_DELAYS = (2.0, 5.0, 15.0)
TRANSIENT_GIT_NETWORK_MARKERS = (
    "connection closed by",
    "connection reset by peer",
    "connection timed out",
    "operation timed out",
    "network is unreachable",
    "could not resolve host",
    "could not resolve hostname",
    "remote end hung up unexpectedly",
    "ssh_exchange_identification: connection closed",
    "kex_exchange_identification: read: connection reset",
    "rpc failed; curl 56",
    "gnutls recv error",
    "tls connection was non-properly terminated",
    "the requested url returned error: 502",
    "the requested url returned error: 503",
    "the requested url returned error: 504",
    "curl 28",
    "curl 52",
    "curl 55",
)


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


def is_transient_git_network_failure(result: dict[str, Any]) -> bool:
    """Return True only for failures that look like temporary network transport errors."""
    if int(result.get("exit_code", 0)) == 0:
        return False
    if bool(result.get("timed_out")):
        return True
    output = str(result.get("output", "")).lower()
    return any(marker in output for marker in TRANSIENT_GIT_NETWORK_MARKERS)


def git_failure_diagnostic(result: dict[str, Any]) -> str:
    """Return non-empty bounded diagnostics even when Git emitted no text."""
    output = str(result.get("output", "")).strip()
    if output:
        return output

    details = [f"exit_code={int(result.get('exit_code', 1))}"]
    if bool(result.get("timed_out")):
        details.append("timed_out=true")
    if bool(result.get("background_process_leak")):
        details.append("background_process_leak=true")
    failure_reason = str(result.get("failure_reason", "")).strip()
    if failure_reason:
        details.append(f"failure_reason={failure_reason}")
    elapsed = result.get("elapsed_seconds")
    if isinstance(elapsed, (int, float)):
        details.append(f"elapsed_seconds={float(elapsed):.3f}")
    return "git failed without output (" + ", ".join(details) + ")"


def run_git_with_network_retry(
    core_module: Any,
    args: list[str],
    cwd: Path,
    *,
    timeout: int = 120,
    retry_delays: tuple[float, ...] = GIT_NETWORK_RETRY_DELAYS,
    log_commands: bool = True,
) -> dict[str, Any]:
    """Run one Git command, retrying only transient transport failures.

    The delays represent retries after the initial attempt, so the default policy is
    four total attempts: immediate, then after 2s, 5s and 15s. Authentication,
    rebase/conflict and other deterministic Git errors are returned immediately.
    Silent terminal failures receive synthetic diagnostic output so callers never
    emit an empty error line.
    """
    result: dict[str, Any] = {}
    for attempt in range(len(retry_delays) + 1):
        result = core_module.process(
            args,
            cwd,
            timeout=timeout,
            log_commands=log_commands,
        )
        if result["exit_code"] == 0:
            return result
        transient = is_transient_git_network_failure(result)
        if not transient or attempt >= len(retry_delays):
            if not str(result.get("output", "")).strip():
                result = dict(result)
                result["output"] = git_failure_diagnostic(result)
            return result

        delay = retry_delays[attempt]
        logger = getattr(core_module, "log", None)
        if callable(logger):
            logger(
                f"transient Git network failure; retrying in {delay:g}s "
                f"(attempt {attempt + 2}/{len(retry_delays) + 1})"
            )
        time.sleep(delay)
    return result


def sync_control(core_module: Any) -> None:
    """Synchronize the active control checkout while preserving its shallow boundary."""
    with core_module.CONTROL_GIT_LOCK:
        branch = core_module.process(
            ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
            core_module.CONTROL,
            timeout=30,
            log_commands=False,
        )
        if (
            branch["exit_code"] != 0
            or str(branch.get("output", "")).strip() != core_module.CONTROL_BRANCH
        ):
            result = core_module.process(
                ["git", "checkout", core_module.CONTROL_BRANCH],
                core_module.CONTROL,
            )
            if result["exit_code"] != 0:
                raise RuntimeError(result["output"])

        result = run_git_with_network_retry(
            core_module,
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
