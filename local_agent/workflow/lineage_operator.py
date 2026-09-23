from __future__ import annotations

import contextlib
import fcntl
import os
from collections.abc import Iterator
from typing import Any

from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore


def _checkpoint_resolution(
    state_payload: dict[str, Any],
    checkpoint_node_id: str,
) -> dict[str, Any]:
    resolutions = state_payload.get("planner_checkpoints")
    if not isinstance(resolutions, dict):
        raise ValueError("workflow planner checkpoint state is unavailable")
    resolution = resolutions.get(checkpoint_node_id)
    if not isinstance(resolution, dict):
        raise ValueError(
            f"planner checkpoint {checkpoint_node_id!r} must be resolved before activation"
        )
    return dict(resolution)


@contextlib.contextmanager
def _activation_lock(
    workflow_store: WorkflowStore,
    workflow_id: str,
) -> Iterator[None]:
    workflow_store.load_manifest(workflow_id)
    root = workflow_store.state_dir / "locks" / "workflow-lineage-operator"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{workflow_id}.lock"
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def activate_next_lineage_revision(
    workflow_store: WorkflowStore,
    workflow_id: str,
) -> dict[str, Any]:
    """Explicitly activate exactly one next append-only workflow revision.

    The first activation is projected from authoritative base state. Later activations
    are projected from authoritative effective state. The outer operator lock prevents
    two explicit activators from observing the same active revision and then advancing
    the lineage twice. Store-level create-only records retain restart idempotency.
    """
    with _activation_lock(workflow_store, workflow_id):
        revision_store = WorkflowRevisionStore(workflow_store)
        activation_store = WorkflowRevisionActivationStore(
            workflow_store,
            revision_store,
        )
        effective_store = WorkflowEffectiveStateStore(
            workflow_store,
            revision_store,
            activation_store,
        )
        revision_chain = revision_store.load(workflow_id)
        if not revision_chain:
            raise ValueError("workflow has no revision available for activation")

        effective_path = workflow_store.root / workflow_id / "effective_state.json"
        if os.path.lexists(effective_path):
            if effective_path.is_symlink() or not effective_path.is_file():
                raise ValueError("effective workflow state path must be a regular file")
            current = effective_store.load(workflow_id)
            target_revision = int(current["active_revision"]) + 1
            if target_revision > len(revision_chain):
                raise ValueError("no next workflow revision exists")
            next_revision = revision_chain[target_revision - 1]
            checkpoint_node_id = str(next_revision["checkpoint_node_id"])
            resolution = _checkpoint_resolution(current, checkpoint_node_id)
            activation = activation_store.append(
                workflow_id,
                target_revision,
                dict(current["node_states"]),
                resolution,
            )
            effective_state = effective_store.activate_next_revision(workflow_id)
            return {
                "workflow_id": workflow_id,
                "activation": activation,
                "effective_state": effective_state,
            }

        base_state = workflow_store.load_state(workflow_id)
        first_revision = revision_chain[0]
        checkpoint_node_id = str(first_revision["checkpoint_node_id"])
        resolution = _checkpoint_resolution(base_state, checkpoint_node_id)
        activation = activation_store.append(
            workflow_id,
            1,
            dict(base_state["node_states"]),
            resolution,
        )
        effective_state = effective_store.initialize(workflow_id)
        return {
            "workflow_id": workflow_id,
            "activation": activation,
            "effective_state": effective_state,
        }
