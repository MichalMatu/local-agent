from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import contract, coordinator, lineage_coordinator, publishing, revisions
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore


BINDING_A = "00000000-0000-4000-8000-000000000121"
BINDING_B = "00000000-0000-4000-8000-000000000122"
WORKFLOW_ID = "lineage-coordinator"


def repository(root: Path, repository_id: str, binding: str) -> RepositoryContext:
    return RepositoryContext(
        repository_id=repository_id,
        repository=f"Owner/{repository_id}",
        control=root / repository_id / "control",
        work=root / repository_id / "work",
        checkpoints=root / repository_id / "checkpoints",
        agent_binding=binding,
    )


def task_node(node_id: str, repository_id: str, binding: str, depends_on: list[str]) -> dict:
    return {
        "id": node_id,
        "kind": "task",
        "repository_id": repository_id,
        "agent_binding": binding,
        "depends_on": depends_on,
        "task": {
            "work_branch": "main",
            "allow_write": False,
            "resources": [],
            "commands": ["true"],
        },
    }


def base_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": WORKFLOW_ID,
        "created_at": "2026-09-19T15:00:00Z",
        "nodes": [
            task_node("audit", "repo-a", BINDING_A, []),
            {
                "id": "review-audit",
                "kind": "planner_checkpoint",
                "depends_on": ["audit"],
            },
        ],
    }


def revision_one(base: dict) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": base["id"],
        "revision": 1,
        "created_at": "2026-09-19T15:01:00Z",
        "parent_digest": contract.manifest_digest(base),
        "checkpoint_node_id": "review-audit",
        "nodes": [
            task_node("implement", "repo-a", BINDING_A, ["review-audit"]),
            {
                "id": "review-implementation",
                "kind": "planner_checkpoint",
                "depends_on": ["implement"],
            },
        ],
    }


def revision_two(base: dict, first: dict) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": base["id"],
        "revision": 2,
        "created_at": "2026-09-19T15:02:00Z",
        "parent_digest": revisions.revision_digest(first),
        "checkpoint_node_id": "review-implementation",
        "nodes": [task_node("verify", "repo-b", BINDING_B, ["review-implementation"])],
    }


class MemoryControlPlane:
    def __init__(self) -> None:
        self.tasks: dict[tuple[str, str], dict] = {}
        self.kinds: dict[tuple[str, str], coordinator.ChildEvidenceKind] = {}
        self.publish_calls: list[tuple[str, str]] = []

    def inspect_child(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_digest: str,
    ) -> coordinator.ChildEvidence:
        key = (repository.repository_id, task_id)
        child = self.tasks.get(key)
        if child is None:
            return coordinator.ChildEvidence(coordinator.ChildEvidenceKind.ABSENT)
        digest = task_digest(child)
        if digest != expected_digest:
            return coordinator.ChildEvidence(
                coordinator.ChildEvidenceKind.DIGEST_MISMATCH,
                task_digest=digest,
            )
        return coordinator.ChildEvidence(
            self.kinds.get(key, coordinator.ChildEvidenceKind.PENDING),
            task_digest=digest,
        )

    def publish_child(self, repository: RepositoryContext, task: dict) -> None:
        key = (repository.repository_id, str(task["id"]))
        if key in self.tasks:
            raise AssertionError("duplicate lineage publication")
        self.tasks[key] = task
        self.publish_calls.append(key)

    def has_unrelated_work(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool:
        return False

    def mark_succeeded(self, repository_id: str, task: dict) -> None:
        key = (repository_id, str(task["id"]))
        if key not in self.tasks:
            raise AssertionError("cannot finish unpublished lineage child")
        self.kinds[key] = coordinator.ChildEvidenceKind.SUCCEEDED


class WorkflowLineageCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workflow_store = WorkflowStore(self.root / "state")
        self.base = base_manifest()
        self.workflow_store.submit(self.base)
        self.revision_store = WorkflowRevisionStore(self.workflow_store)
        self.activation_store = WorkflowRevisionActivationStore(
            self.workflow_store,
            self.revision_store,
        )
        self.effective_store = WorkflowEffectiveStateStore(
            self.workflow_store,
            self.revision_store,
            self.activation_store,
        )
        self.repositories = [
            repository(self.root, "repo-a", BINDING_A),
            repository(self.root, "repo-b", BINDING_B),
        ]
        self.control = MemoryControlPlane()

    def prepare_revision_one(self) -> dict:
        for target in ("dispatched", "running", "succeeded"):
            self.workflow_store.set_node_state(WORKFLOW_ID, "audit", target)
        resolution = self.workflow_store.resolve_planner_checkpoint(
            WORKFLOW_ID,
            "review-audit",
            resolver="chatgpt-planner",
            note="Audit accepted.",
        )
        first = revision_one(self.base)
        self.revision_store.append(WORKFLOW_ID, first)
        base_states = dict(self.workflow_store.load_state(WORKFLOW_ID)["node_states"])
        self.activation_store.append(
            WORKFLOW_ID,
            1,
            base_states,
            resolution,
            activated_at="2026-09-19T15:03:00Z",
        )
        self.effective_store.initialize(WORKFLOW_ID)
        return first

    def test_revision_one_and_two_execute_with_stable_child_identity(self) -> None:
        first = self.prepare_revision_one()
        implement_before = publishing.materialize_lineage_child_task(
            self.base,
            [first],
            "implement",
        )

        first_tick = lineage_coordinator.tick_lineage_workflow(
            self.effective_store,
            WORKFLOW_ID,
            self.repositories,
            self.control,
        )
        self.assertEqual(first_tick.published, ("implement",))
        self.control.mark_succeeded("repo-a", implement_before)
        lineage_coordinator.tick_lineage_workflow(
            self.effective_store,
            WORKFLOW_ID,
            self.repositories,
            self.control,
        )
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["node_states"]["review-implementation"],
            "waiting_planner",
        )

        resolution = self.effective_store.resolve_planner_checkpoint(
            WORKFLOW_ID,
            "review-implementation",
            resolver="chatgpt-planner",
            resolved_at="2026-09-19T15:04:00Z",
        )
        current = self.effective_store.load(WORKFLOW_ID)
        second = revision_two(self.base, first)
        self.revision_store.append(WORKFLOW_ID, second)
        self.activation_store.append(
            WORKFLOW_ID,
            2,
            dict(current["node_states"]),
            resolution,
            activated_at="2026-09-19T15:04:01Z",
        )
        self.effective_store.activate_next_revision(WORKFLOW_ID)

        implement_after = publishing.materialize_lineage_child_task(
            self.base,
            [first, second],
            "implement",
        )
        self.assertEqual(implement_after, implement_before)

        second_tick = lineage_coordinator.tick_lineage_workflow(
            self.effective_store,
            WORKFLOW_ID,
            self.repositories,
            self.control,
        )
        self.assertEqual(second_tick.published, ("verify",))
        self.assertEqual(
            [repository_id for repository_id, _task_id in self.control.publish_calls],
            ["repo-a", "repo-b"],
        )
        self.assertEqual(len(self.control.publish_calls), 2)

        verify = publishing.materialize_lineage_child_task(
            self.base,
            [first, second],
            "verify",
        )
        self.control.mark_succeeded("repo-b", verify)
        lineage_coordinator.tick_lineage_workflow(
            self.effective_store,
            WORKFLOW_ID,
            self.repositories,
            self.control,
        )
        final = self.effective_store.load(WORKFLOW_ID)
        self.assertEqual(final["workflow_state"], "completed")
        self.assertEqual(final["node_states"]["implement"], "succeeded")
        self.assertEqual(final["node_states"]["verify"], "succeeded")

    def test_existing_revision_child_is_reconciled_after_effective_store_restart(self) -> None:
        first = self.prepare_revision_one()
        child = publishing.materialize_lineage_child_task(self.base, [first], "implement")
        self.control.publish_child(self.repositories[0], child)

        restarted = WorkflowEffectiveStateStore(
            WorkflowStore(self.root / "state"),
        )
        tick = lineage_coordinator.tick_lineage_workflow(
            restarted,
            WORKFLOW_ID,
            self.repositories,
            self.control,
        )
        self.assertEqual(tick.reconciled, ("implement",))
        self.assertEqual(len(self.control.publish_calls), 1)
        self.assertEqual(
            restarted.load(WORKFLOW_ID)["node_states"]["implement"],
            "dispatched",
        )


if __name__ == "__main__":
    unittest.main()
