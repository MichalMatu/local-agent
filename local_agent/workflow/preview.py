from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from local_agent.workflow import contract, state


@dataclass(frozen=True, slots=True)
class WorkflowPreview:
    waves: tuple[tuple[str, ...], ...]
    final_state: str
    waiting_nodes: tuple[str, ...]


def preview_workflow(manifest: dict[str, Any]) -> WorkflowPreview:
    """Simulate successful task completion without performing any side effects.

    The preview is intentionally conservative: at most one task per repository is placed
    in a wave. User gates and planner checkpoints stop simulation rather than being
    automatically approved. Barriers retain normal state-machine semantics.
    """
    contract.validate_workflow_manifest(manifest)
    nodes = {str(node["id"]): node for node in manifest["nodes"]}
    node_states = state.initial_node_states(manifest)
    waves: list[tuple[str, ...]] = []

    while True:
        workflow_state = state.workflow_state(node_states)
        waiting_nodes = tuple(
            node_id
            for node_id, node_state in node_states.items()
            if node_state in {"waiting_user", "waiting_planner"}
        )
        if waiting_nodes:
            return WorkflowPreview(
                waves=tuple(waves),
                final_state=workflow_state,
                waiting_nodes=waiting_nodes,
            )
        if workflow_state in {"completed", "failed", "cancelled"}:
            return WorkflowPreview(
                waves=tuple(waves),
                final_state=workflow_state,
                waiting_nodes=(),
            )

        selected: list[str] = []
        repositories: set[str] = set()
        for node_id, node in nodes.items():
            if node_states[node_id] != "ready" or node["kind"] != "task":
                continue
            repository_id = str(node["repository_id"])
            if repository_id in repositories:
                continue
            repositories.add(repository_id)
            selected.append(node_id)

        if not selected:
            return WorkflowPreview(
                waves=tuple(waves),
                final_state=workflow_state,
                waiting_nodes=(),
            )

        waves.append(tuple(selected))
        for node_id in selected:
            node_states[node_id] = state.transition_node_state(
                node_states[node_id],
                "succeeded",
            )
        node_states = state.advance_dependency_states(manifest, node_states)
