from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from local_agent.repository.context import RepositoryContext, validate_repository_set
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import publishing
from local_agent.workflow.evidence import ChildEvidence, ChildEvidenceKind
from local_agent.workflow.store import WorkflowStore


class WorkflowIntegrityError(RuntimeError):
    """Raised when durable workflow state conflicts with exact repository evidence."""


@dataclass(frozen=True, slots=True)
class TickResult:
    published: tuple[str, ...] = ()
    reconciled: tuple[str, ...] = ()
    deferred_same_repository: tuple[str, ...] = ()
    deferred_unrelated_work: tuple[str, ...] = ()
    integrity_failures: tuple[str, ...] = ()


class WorkflowControlPlane(Protocol):
    """Side-effect boundary used by the workflow coordinator.

    The coordinator owns graph policy. A concrete adapter owns repository evidence and
    publication. No production adapter is wired into the supervisor yet.
    """

    def inspect_child(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_digest: str,
    ) -> ChildEvidence: ...

    def publish_child(
        self,
        repository: RepositoryContext,
        task: dict[str, Any],
    ) -> None: ...

    def has_unrelated_work(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool: ...


def _task_nodes(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in manifest["nodes"] if node["kind"] == "task"]


def _repository_map(
    repositories: list[RepositoryContext],
) -> dict[str, RepositoryContext]:
    validated = validate_repository_set(repositories)
    return {repository.repository_id: repository for repository in validated}


def _repository_for_node(
    repositories: dict[str, RepositoryContext],
    node: dict[str, Any],
) -> RepositoryContext:
    repository_id = str(node["repository_id"])
    repository = repositories.get(repository_id)
    if repository is None:
        raise WorkflowIntegrityError(
            f"workflow target repository is not enabled with exact id {repository_id!r}"
        )
    expected_binding = str(node["agent_binding"])
    if repository.agent_binding != expected_binding:
        raise WorkflowIntegrityError(
            f"workflow target binding mismatch for {repository_id!r}: "
            f"expected {expected_binding}, got {repository.agent_binding or 'unbound'}"
        )
    return repository


def _validated_evidence(
    child_evidence: ChildEvidence,
    *,
    expected_digest: str,
) -> ChildEvidence:
    if not isinstance(child_evidence, ChildEvidence):
        raise WorkflowIntegrityError("control plane returned invalid child evidence")
    if child_evidence.kind in {
        ChildEvidenceKind.ABSENT,
        ChildEvidenceKind.DIGEST_MISMATCH,
    }:
        return child_evidence
    if child_evidence.task_digest != expected_digest:
        raise WorkflowIntegrityError(
            "control plane evidence did not carry the exact expected task digest"
        )
    return child_evidence


def _reconciliation_target(
    current: str,
    child_evidence: ChildEvidence,
    *,
    node_id: str,
) -> str | None:
    if child_evidence.kind == ChildEvidenceKind.ABSENT:
        if current in {"dispatched", "running"}:
            raise WorkflowIntegrityError(
                f"workflow child {node_id!r} is missing after dispatch; refusing replay"
            )
        return None
    if child_evidence.kind == ChildEvidenceKind.DIGEST_MISMATCH:
        return "failed"
    if child_evidence.kind == ChildEvidenceKind.PENDING:
        return "running" if current == "running" else "dispatched"
    if child_evidence.kind == ChildEvidenceKind.RUNNING:
        return "running"
    if child_evidence.kind == ChildEvidenceKind.SUCCEEDED:
        return "succeeded"
    if child_evidence.kind == ChildEvidenceKind.FAILED:
        return "failed"
    if child_evidence.kind == ChildEvidenceKind.CANCELLED:
        return "cancelled"
    if child_evidence.kind == ChildEvidenceKind.INTERRUPTED:
        return "blocked_interrupted"
    raise WorkflowIntegrityError(f"unsupported child evidence for {node_id!r}")


def _reconcile_one(
    store: WorkflowStore,
    workflow_id: str,
    manifest: dict[str, Any],
    node: dict[str, Any],
    repository: RepositoryContext,
    control_plane: WorkflowControlPlane,
    current_state: str,
) -> tuple[dict[str, Any] | None, bool]:
    node_id = str(node["id"])
    child = publishing.materialize_child_task(manifest, node_id)
    expected_digest = task_digest(child)
    child_evidence = _validated_evidence(
        control_plane.inspect_child(repository, str(child["id"]), expected_digest),
        expected_digest=expected_digest,
    )
    target = _reconciliation_target(
        current_state,
        child_evidence,
        node_id=node_id,
    )
    if target is None or target == current_state:
        return None, child_evidence.kind == ChildEvidenceKind.DIGEST_MISMATCH
    updated = store.set_node_state(workflow_id, node_id, target)
    return updated, child_evidence.kind == ChildEvidenceKind.DIGEST_MISMATCH


def tick_workflow(
    store: WorkflowStore,
    workflow_id: str,
    repositories: list[RepositoryContext],
    control_plane: WorkflowControlPlane,
) -> TickResult:
    """Reconcile and dispatch one durable workflow tick.

    This function is intentionally supervisor-independent. The caller supplies both
    repository identities and a control-plane adapter. Until a production adapter is
    added and explicitly wired, this code cannot publish into a live project repo.
    """
    published: list[str] = []
    reconciled: list[str] = []
    deferred_same_repository: list[str] = []
    deferred_unrelated_work: list[str] = []
    integrity_failures: list[str] = []

    with store.execution_lock(workflow_id):
        manifest = store.load_manifest(workflow_id)
        repository_by_id = _repository_map(repositories)
        nodes = _task_nodes(manifest)
        current = store.load_state(workflow_id)

        # First recover exact evidence for any node that could already have been
        # published. This includes ready nodes because a prior process may have died
        # after remote publication but before its local state transition.
        for node in nodes:
            node_id = str(node["id"])
            node_state = str(current["node_states"][node_id])
            if node_state not in {"ready", "dispatched", "running"}:
                continue
            repository = _repository_for_node(repository_by_id, node)
            updated, integrity_failure = _reconcile_one(
                store,
                workflow_id,
                manifest,
                node,
                repository,
                control_plane,
                node_state,
            )
            if integrity_failure:
                integrity_failures.append(node_id)
            if updated is not None:
                current = updated
                reconciled.append(node_id)

        current = store.load_state(workflow_id)
        if current["cancel_requested"] or current["workflow_state"] not in {
            "pending",
            "running",
        }:
            return TickResult(
                published=tuple(published),
                reconciled=tuple(reconciled),
                deferred_same_repository=tuple(deferred_same_repository),
                deferred_unrelated_work=tuple(deferred_unrelated_work),
                integrity_failures=tuple(integrity_failures),
            )

        # A repository with an already dispatched/running workflow child is reserved
        # for this tick. V1 never queues a second workflow-owned child into one repo.
        reserved_repositories = {
            str(node["repository_id"])
            for node in nodes
            if current["node_states"][str(node["id"])] in {"dispatched", "running"}
        }

        for node in nodes:
            node_id = str(node["id"])
            current = store.load_state(workflow_id)
            if current["cancel_requested"] or current["workflow_state"] not in {
                "pending",
                "running",
            }:
                break
            if current["node_states"][node_id] != "ready":
                continue

            repository = _repository_for_node(repository_by_id, node)
            if repository.repository_id in reserved_repositories:
                deferred_same_repository.append(node_id)
                continue

            child = publishing.materialize_child_task(manifest, node_id)
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
                updated = store.set_node_state(workflow_id, node_id, target)
                reconciled.append(node_id)
                if child_evidence.kind == ChildEvidenceKind.DIGEST_MISMATCH:
                    integrity_failures.append(node_id)
                if updated["node_states"][node_id] in {"dispatched", "running"}:
                    reserved_repositories.add(repository.repository_id)
                continue

            if control_plane.has_unrelated_work(repository, str(child["id"])):
                deferred_unrelated_work.append(node_id)
                continue

            # Publication must complete before local state changes. If the process
            # dies after the remote write, the next tick observes the deterministic
            # child id/digest and recovers without publishing again.
            control_plane.publish_child(repository, child)
            store.set_node_state(workflow_id, node_id, "dispatched")
            published.append(node_id)
            reserved_repositories.add(repository.repository_id)

    return TickResult(
        published=tuple(published),
        reconciled=tuple(reconciled),
        deferred_same_repository=tuple(deferred_same_repository),
        deferred_unrelated_work=tuple(deferred_unrelated_work),
        integrity_failures=tuple(integrity_failures),
    )
