from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import publishing, revisions
from local_agent.workflow.coordinator import (
    WorkflowIntegrityError,
    _repository_for_node,
    _repository_map,
)
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.git_cancellation import (
    CancelRequestEvidence,
    CancelRequestState,
)


class WorkflowCancellationTransport(Protocol):
    def request_cancel(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_task_digest: str,
    ) -> CancelRequestEvidence: ...


@dataclass(frozen=True, slots=True)
class CancellationTickResult:
    requested: tuple[str, ...] = ()
    deferred: tuple[str, ...] = ()
    accepted: tuple[str, ...] = ()
    completed: tuple[str, ...] = ()
    rejected: tuple[str, ...] = ()
    not_needed: tuple[str, ...] = ()


def _active_graph(
    store: WorkflowEffectiveStateStore,
    workflow_id: str,
    current: dict,
) -> tuple[dict, list[dict]]:
    base = store.workflow_store.load_manifest(workflow_id)
    chain = store.revision_store.load(workflow_id)
    active_revision = int(current["active_revision"])
    if active_revision < 1 or active_revision > len(chain):
        raise WorkflowIntegrityError("effective workflow active revision is unavailable")
    active_chain = chain[:active_revision]
    return revisions.effective_manifest(base, active_chain), active_chain


def request_lineage_cancellations(
    store: WorkflowEffectiveStateStore,
    workflow_id: str,
    repositories: list[RepositoryContext],
    transport: WorkflowCancellationTransport,
) -> CancellationTickResult:
    """Request exact cancellation for active children of a cancelled lineage graph.

    This helper is deliberately separate from normal lineage reconciliation and from
    production runtime entrypoints. It never mutates node state from ACK evidence. The
    ordinary lineage coordinator remains responsible for observing exact terminal task
    results such as `cancelled_by_operator`.
    """
    buckets: dict[CancelRequestState, list[str]] = {
        state: [] for state in CancelRequestState
    }

    with store.workflow_store.execution_lock(workflow_id):
        current = store.load(workflow_id)
        if not current["cancel_requested"]:
            return CancellationTickResult()

        manifest, active_chain = _active_graph(store, workflow_id, current)
        repositories_by_id = _repository_map(repositories)
        base = store.workflow_store.load_manifest(workflow_id)

        for node in manifest["nodes"]:
            if node["kind"] != "task":
                continue
            node_id = str(node["id"])
            if current["node_states"][node_id] not in {"dispatched", "running"}:
                continue

            repository = _repository_for_node(repositories_by_id, node)
            child = publishing.materialize_lineage_child_task(
                base,
                active_chain,
                node_id,
            )
            expected_digest = task_digest(child)
            result = transport.request_cancel(
                repository,
                str(child["id"]),
                expected_digest,
            )
            if not isinstance(result, CancelRequestEvidence):
                raise WorkflowIntegrityError(
                    f"cancellation transport returned invalid evidence for {node_id!r}"
                )
            if result.task_id != child["id"]:
                raise WorkflowIntegrityError(
                    f"cancellation transport returned wrong task id for {node_id!r}"
                )
            buckets[result.state].append(node_id)

    return CancellationTickResult(
        requested=tuple(buckets[CancelRequestState.REQUESTED]),
        deferred=tuple(buckets[CancelRequestState.DEFERRED]),
        accepted=tuple(buckets[CancelRequestState.ACCEPTED]),
        completed=tuple(buckets[CancelRequestState.COMPLETED]),
        rejected=tuple(buckets[CancelRequestState.REJECTED]),
        not_needed=tuple(buckets[CancelRequestState.NOT_NEEDED]),
    )
