from __future__ import annotations

from pathlib import Path
from typing import Any

from local_agent.conversation import contract, records
from local_agent.foundation import result_events


def build_child_terminal_attention_event(
    request: dict[str, Any],
    terminal: dict[str, Any],
    *,
    emitted_at: str | None = None,
) -> dict[str, Any]:
    """Build one bounded hint for the exact parent of a durable child terminal.

    The event is notification-only. Durable child/workflow records remain authoritative.
    """

    contract.validate_child_request(request)
    records.validate_child_terminal(terminal, request=request)
    return result_events.build_child_terminal_event(
        parent_conversation_url=request["parent_conversation_url"],
        workflow_id=request["workflow_id"],
        workflow_node_id=request["workflow_node_id"],
        child_request_id=request["id"],
        child_request_digest=contract.child_request_digest(request),
        terminal_digest=records.child_terminal_digest(terminal, request=request),
        outcome=terminal["outcome"],
        emitted_at=emitted_at,
    )


def enqueue_child_terminal_attention(
    request: dict[str, Any],
    terminal: dict[str, Any],
    *,
    state_dir: Path,
) -> dict[str, Any]:
    event = build_child_terminal_attention_event(request, terminal)
    result_events.enqueue_event(event, state_dir=state_dir)
    return event
