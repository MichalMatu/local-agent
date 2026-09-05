#!/usr/bin/env python3
"""Root import surface for repository-independent remote operator control."""

from local_agent.operator.remote import (
    POLL_SECONDS,
    REMOTE_BRANCH,
    REMOTE_STATE_PATH,
    RemoteOperatorState,
    _git,
    _load_remote_payload,
    _remote_ref,
    _validated_state,
    poll_remote_operator,
)

__all__ = [
    "POLL_SECONDS",
    "REMOTE_BRANCH",
    "REMOTE_STATE_PATH",
    "RemoteOperatorState",
    "_git",
    "_load_remote_payload",
    "_remote_ref",
    "_validated_state",
    "poll_remote_operator",
]
