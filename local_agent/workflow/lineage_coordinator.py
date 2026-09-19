from __future__ import annotations

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import publishing, revisions
from local_agent.workflow.coordinator import (
    TickResult,
    WorkflowControlPlane,
    _reconciliation_target,
    _repository_for_node,
    _repository_map,
    _validated_evidence,
)
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.evidence import ChildEvidenceKind


def _active_graph(
    store: WorkflowEffectiveStateStore,
    workflow_id: str,
    current: dict,
) -> tuple[dict, list[dict]]:
    base = store.workflow_store.load_manifest(workflow_id)
    chain = store.revision_store.load(workflow_id)
    active_revision = int(current["active_revision"])
    if active_revision < 1 or active_revision > len(chain):
        raise ValueError("effective workflow active revision is unavailable")
    active_chain = chain[:active_revision]
    return revisions.effective_manifest(base, active_chain), active_chain


def _task_nodes(manifest: dict) -> list[dict]:
    return [node for node in manifest["nodes"] if node["kind"] == "task"]


def _child(
    store: WorkflowEffectiveStateStore,
    workflow_id: str,
    chain: list[dict],
    node_id: str,
) -> dict:
    base = store.workflow_store.load_manifest(workflow_id)
    return publishing.materialize_lineage_child_task(base, chain, node_id)


def tick_lineage_workflow(
    store: WorkflowEffectiveStateStore,
    workflow_id: str,
    repositories: list[RepositoryContext],
    control_plane: WorkflowControlPlane,
) -> TickResult:
    """Reconcile and dispatch one tick for an already activated revision graph.

    This coordinator is intentionally separate from the production/static path. It has
    no supervisor wiring and requires an explicitly supplied control-plane adapter.
    """
    published: list[str] = []
    reconciled: list[str] = []
    deferred_same_repository: list[str] = []
    deferred_unrelated_work: list[str] = []
    integrity_failures: list[str] = []

    # Reuse the workflow-wide execution lock so local cancellation/checkpoint/revision
    # activation cannot race a future dispatch integration. The effective-state store
    # also serializes its own file mutations independently.
    with store.workflow_store.execution_lock(workflow_id):
        current = store.load(workflow_id)
        manifest, chain = _active_graph(store, workflow_id, current)
        repositories_by_id = _repository_map(repositories)
        nodes = _task_nodes(manifest)

        for node in nodes:
            node_id = str(node["id"])
            node_state = str(current["node_states"][node_id])
            if node_state not in {"ready", "dispatched", "running"}:
                continue
            repository = _repository_for_node(repositories_by_id, node)
            child = _child(store, workflow_id, chain, node_id)
            expected_digest = task_digest(child)
            child_evidence = _validated_evidence(
                control_plane.inspect_child(
                    repository,
                    str(child["id"]),
                    expected_digest,
                ),
                expected_digest=expected_digest,
            )
            target = _reconciliation_target(
                node_state,
                child_evidence,
                node_id=node_id,
            )
            if child_evidence.kind == ChildEvidenceKind.DIGEST_MISMATCH:
                integrity_failures.append(node_id)
            if target is not None and target != node_state:
                current = store.set_task_node_state(workflow_id, node_id, target)
                reconciled.append(node_id)

        current = store.load(workflow_id)
        if current["workflow_state"] not in {"pending", "running"}:
            return TickResult(
                published=tuple(published),
                reconciled=tuple(reconciled),
                deferred_same_repository=tuple(deferred_same_repository),
                deferred_unrelated_work=tuple(deferred_unrelated_work),
                integrity_failures=tuple(integrity_failures),
            )

        reserved_repositories = {
            str(node["repository_id"])
            for node in nodes
            if current["node_states"][str(node["id"])] in {"dispatched", "running"}
        }

        for node in nodes:
            node_id = str(node["id"])
            current = store.load(workflow_id)
            if current["workflow_state"] not in {"pending", "running"}:
                break
            if current["node_states"][node_id] != "ready":
                continue

            repository = _repository_for_node(repositories_by_id, node)
            if repository.repository_id in reserved_repositories:
                deferred_same_repository.append(node_id)
                continue

            child = _child(store, workflow_id, chain, node_id)
            expected_digest = task_digest(child)
            child_evidence = _validated_evidence(
                control_plane.inspect_child(
                    repository,
                    str(child["id"]),
                    expected_digest,
                ),
                expected_digest=expected_digest,
            )
            target = _reconciliation_target(
                "ready",
                child_evidence,
                node_id=node_id,
            )
            if target is not None:
                updated = store.set_task_node_state(workflow_id, node_id, target)
                reconciled.append(node_id)
                if child_evidence.kind == ChildEvidenceKind.DIGEST_MISMATCH:
                    integrity_failures.append(node_id)
                if updated["node_states"][node_id] in {"dispatched", "running"}:
                    reserved_repositories.add(repository.repository_id)
                continue

            if control_plane.has_unrelated_work(repository, str(child["id"])):
                deferred_unrelated_work.append(node_id)
                continue

            control_plane.publish_child(repository, child)
            store.set_task_node_state(workflow_id, node_id, "dispatched")
            published.append(node_id)
            reserved_repositories.add(repository.repository_id)

    return TickResult(
        published=tuple(published),
        reconciled=tuple(reconciled),
        deferred_same_repository=tuple(deferred_same_repository),
        deferred_unrelated_work=tuple(deferred_unrelated_work),
        integrity_failures=tuple(integrity_failures),
    )
