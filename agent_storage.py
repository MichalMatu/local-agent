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
CONTROL_RECOVERABLE_DIRS = (
    ".agent/status",
    ".agent/runs",
    ".agent/results",
    ".agent/daemon/acks",
)
CONTROL_RECOVERABLE_UNTRACKED_BASENAMES = frozenset({".DS_Store"})
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


def _control_status_entries(core_module: Any) -> tuple[tuple[str, str], ...]:
    """Return exact porcelain status entries without Git path quoting."""
    status = core_module.process(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        core_module.CONTROL,
        timeout=30,
        log_commands=False,
    )
    if status["exit_code"] != 0:
        raise RuntimeError(git_failure_diagnostic(status))

    fields = str(status.get("output", "")).split("\0")
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(fields):
        record = fields[index]
        if not record:
            index += 1
            continue
        if len(record) < 4 or record[2] != " ":
            raise RuntimeError(f"invalid git status porcelain record: {record!r}")
        code = record[:2]
        path = record[3:]
        if not path:
            raise RuntimeError("invalid git status porcelain path")
        entries.append((code, path))

        if "R" in code or "C" in code:
            index += 1
            if index >= len(fields) or not fields[index]:
                raise RuntimeError("incomplete git status rename/copy record")
            entries.append((code, fields[index]))
        index += 1
    return tuple(entries)


def _control_dirty_paths(core_module: Any) -> tuple[str, ...]:
    return tuple(sorted({path for _code, path in _control_status_entries(core_module)}))


def _recoverable_control_path(path: str) -> bool:
    return any(
        path == directory or path.startswith(directory + "/")
        for directory in CONTROL_RECOVERABLE_DIRS
    )


def _recoverable_untracked_control_noise(code: str, path: str) -> bool:
    return (
        code == "??"
        and Path(path).name in CONTROL_RECOVERABLE_UNTRACKED_BASENAMES
    )


def recover_daemon_owned_control_changes(core_module: Any) -> None:
    """Discard interrupted daemon artifacts and explicitly allowlisted host noise."""
    entries = _control_status_entries(core_module)
    if not entries:
        return

    dirty = tuple(sorted({path for _code, path in entries}))
    unexpected = tuple(
        path
        for code, path in entries
        if not _recoverable_control_path(path)
        and not _recoverable_untracked_control_noise(code, path)
    )
    if unexpected:
        raise RuntimeError(
            "control checkout has unexpected local changes: "
            + ", ".join(unexpected)
        )

    logger = getattr(core_module, "log", None)
    if callable(logger):
        logger(
            "recovering safe control checkout changes before sync: "
            + ", ".join(dirty)
        )

    tracked = tuple(sorted({path for code, path in entries if code != "??"}))
    untracked = tuple(sorted({path for code, path in entries if code == "??"}))

    if tracked:
        restore = core_module.process(
            [
                "git",
                "restore",
                "--source=HEAD",
                "--staged",
                "--worktree",
                "--",
                *tracked,
            ],
            core_module.CONTROL,
            timeout=30,
            log_commands=False,
        )
        if restore["exit_code"] != 0:
            raise RuntimeError(git_failure_diagnostic(restore))

    if untracked:
        clean = core_module.process(
            ["git", "clean", "-fd", "--", *untracked],
            core_module.CONTROL,
            timeout=30,
            log_commands=False,
        )
        if clean["exit_code"] != 0:
            raise RuntimeError(git_failure_diagnostic(clean))

    remaining = _control_dirty_paths(core_module)
    if remaining:
        raise RuntimeError(
            "control checkout remained dirty after daemon-owned recovery: "
            + ", ".join(remaining)
        )


def materialize_control_remote_tracking_ref(core_module: Any) -> None:
    """Persist the exact FETCH_HEAD as origin/<control-branch> after a successful pull.

    Single-branch shallow control clones do not always retain a remote-tracking ref.
    ACK verification intentionally reads the fetched remote tree, so materializing the
    ref removes the `Not a valid object name origin/agent-control` failure without
    weakening ACK semantics to a possibly-unpushed local commit.
    """
    fetched = core_module.process(
        ["git", "rev-parse", "FETCH_HEAD"],
        core_module.CONTROL,
        timeout=30,
        log_commands=False,
    )
    if fetched["exit_code"] != 0:
        raise RuntimeError(git_failure_diagnostic(fetched))
    sha = str(fetched.get("output", "")).strip()
    if len(sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
        raise RuntimeError(f"invalid FETCH_HEAD after control pull: {sha!r}")
    remote_ref = f"refs/remotes/origin/{core_module.CONTROL_BRANCH}"
    updated = core_module.process(
        ["git", "update-ref", remote_ref, sha],
        core_module.CONTROL,
        timeout=30,
        log_commands=False,
    )
    if updated["exit_code"] != 0:
        raise RuntimeError(git_failure_diagnostic(updated))


def sync_control(core_module: Any) -> None:
    """Synchronize the active control checkout while preserving its shallow boundary."""
    with core_module.CONTROL_GIT_LOCK:
        recover_daemon_owned_control_changes(core_module)
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
        materialize_control_remote_tracking_ref(core_module)

    try:
        from agent_cleanup import prune_control_runtime

        prune_control_runtime(core_module)
    except Exception as exc:
        logger = getattr(core_module, "log", None)
        if callable(logger):
            logger(f"runtime GC skipped after sync: {type(exc).__name__}: {exc}")


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
