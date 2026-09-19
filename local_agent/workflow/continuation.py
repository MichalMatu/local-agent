from __future__ import annotations

from typing import Any, Iterable

from local_agent.workflow import revisions, state


def project_next_revision_states(
    base_manifest: dict[str, Any],
    prior_revisions: Iterable[dict[str, Any]],
    next_revision: dict[str, Any],
    current_states: dict[str, str],
) -> dict[str, str]:
    """Project activation of exactly one append-only revision without persisting it.

    The caller supplies authoritative states for the graph before the new revision. The
    referenced planner checkpoint must already be succeeded. Existing node states are
    immutable inputs; only newly appended nodes start at pending and are advanced by the
    normal dependency state machine.
    """
    prior = list(prior_revisions)
    before = revisions.effective_manifest(base_manifest, prior)
    revisions.validate_revision_sequence(base_manifest, [*prior, next_revision])
    after = revisions.effective_manifest(base_manifest, [*prior, next_revision])

    before_ids = {str(node["id"]) for node in before["nodes"]}
    if not isinstance(current_states, dict) or set(current_states) != before_ids:
        missing = sorted(before_ids - set(current_states)) if isinstance(current_states, dict) else []
        extra = sorted(set(current_states) - before_ids) if isinstance(current_states, dict) else []
        raise ValueError(
            f"continuation current states do not match prior graph: missing={missing!r} extra={extra!r}"
        )

    # Validate all existing state values using the real state machine before projecting.
    state.advance_dependency_states(before, dict(current_states))

    checkpoint_id = str(next_revision["checkpoint_node_id"])
    if current_states.get(checkpoint_id) != "succeeded":
        raise ValueError(
            f"continuation checkpoint {checkpoint_id!r} must be succeeded before activation"
        )

    projected = dict(current_states)
    new_ids: list[str] = []
    for node in next_revision["nodes"]:
        node_id = str(node["id"])
        if node_id in projected:
            raise ValueError(f"continuation attempted to replace existing node state: {node_id!r}")
        projected[node_id] = "pending"
        new_ids.append(node_id)

    advanced = state.advance_dependency_states(after, projected)
    for node_id in before_ids:
        if advanced[node_id] != current_states[node_id]:
            raise ValueError(
                f"continuation changed existing node state {node_id!r}: "
                f"{current_states[node_id]!r} -> {advanced[node_id]!r}"
            )
    if not new_ids:
        raise ValueError("continuation revision must append at least one node")
    return advanced
