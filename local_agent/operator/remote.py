"""Repository-independent remote emergency operator control."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import agent_core as core
import agent_operator

REMOTE_BRANCH = "operator-control"
REMOTE_STATE_PATH = ".agent/operator/state.json"
POLL_SECONDS = 2.0
_CONTROL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass
class RemoteOperatorState:
    last_poll_at: float | None = None
    last_ref: str | None = None
    desired_state: str | None = None
    request_id: str | None = None


def _git(args: list[str], self_repo: Path, *, timeout: int = 30) -> dict[str, Any]:
    return core.process(
        ["git", *args],
        self_repo,
        timeout=timeout,
        log_commands=False,
    )


def _remote_ref(self_repo: Path) -> str:
    result = _git(
        ["ls-remote", "--heads", "origin", f"refs/heads/{REMOTE_BRANCH}"],
        self_repo,
        timeout=15,
    )
    if result["exit_code"] != 0:
        raise RuntimeError(
            str(result.get("output", "")).strip() or "operator control ref probe failed"
        )
    output = str(result.get("output", "")).strip()
    if not output:
        raise RuntimeError(f"remote operator branch is missing: {REMOTE_BRANCH}")
    ref = output.split()[0]
    if len(ref) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in ref):
        raise RuntimeError(f"invalid operator control ref: {ref!r}")
    return ref.lower()


def _load_remote_payload(self_repo: Path, ref: str) -> dict[str, Any]:
    fetch = _git(
        [
            "fetch",
            "--quiet",
            "--no-tags",
            "origin",
            f"refs/heads/{REMOTE_BRANCH}",
        ],
        self_repo,
        timeout=30,
    )
    if fetch["exit_code"] != 0:
        raise RuntimeError(str(fetch.get("output", "")).strip() or "operator control fetch failed")
    resolved = _git(["rev-parse", "FETCH_HEAD"], self_repo, timeout=10)
    fetched_ref = str(resolved.get("output", "")).strip().lower()
    if resolved["exit_code"] != 0 or fetched_ref != ref:
        raise RuntimeError(
            f"operator control ref changed during fetch: expected={ref} "
            f"got={fetched_ref or 'unknown'}"
        )
    show = _git(["show", f"FETCH_HEAD:{REMOTE_STATE_PATH}"], self_repo, timeout=15)
    if show["exit_code"] != 0:
        raise ValueError(str(show.get("output", "")).strip() or "operator control state missing")
    payload = json.loads(str(show.get("output", "")))
    if not isinstance(payload, dict):
        raise ValueError("operator control state root must be an object")
    return payload


def _validated_state(payload: dict[str, Any]) -> tuple[str, str]:
    if payload.get("version") != 1:
        raise ValueError("operator control version must be 1")
    desired_state = payload.get("desired_state")
    if desired_state not in {"enabled", "disabled"}:
        raise ValueError("operator desired_state must be enabled or disabled")
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not _CONTROL_ID_RE.fullmatch(request_id):
        raise ValueError("operator request_id is invalid")
    return desired_state, request_id


def poll_remote_operator(
    state: RemoteOperatorState,
    *,
    self_repo: Path,
    now: float | None = None,
    force: bool = False,
) -> str | None:
    """Refresh central desired state and persist disable locally when requested.

    Remote ``enabled`` never clears the local marker. Re-enabling always requires
    an explicit local operator action after the remote desired state was cleared.
    """
    current = time.monotonic() if now is None else now
    due = (
        force
        or state.last_poll_at is None
        or current - state.last_poll_at >= POLL_SECONDS
    )
    if due:
        state.last_poll_at = current
        try:
            ref = _remote_ref(self_repo)
        except Exception as exc:
            core.log(f"remote operator ref probe degraded: {type(exc).__name__}: {exc}")
        else:
            if ref != state.last_ref or state.desired_state is None:
                try:
                    payload = _load_remote_payload(self_repo, ref)
                    desired_state, request_id = _validated_state(payload)
                except ValueError as exc:
                    state.last_ref = ref
                    state.desired_state = "disabled"
                    state.request_id = f"invalid-{ref[:12]}"
                    core.log(f"remote operator state invalid; failing closed: {exc}")
                except Exception as exc:
                    core.log(
                        "remote operator control refresh degraded: "
                        f"{type(exc).__name__}: {exc}"
                    )
                else:
                    state.last_ref = ref
                    state.desired_state = desired_state
                    state.request_id = request_id

    if state.desired_state == "disabled":
        if not agent_operator.is_disabled():
            agent_operator.disable_agent(
                control_id=state.request_id,
                reason="remote_operator_control",
            )
        return "disabled"
    return state.desired_state
