from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import contract, coordinator, lineage_coordinator, publishing
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore


BINDING = "00000000-0000-4000-8000-000000000131"
WORKFLOW_ID = "lineage-cancellation"


def repository(root: Path) -> RepositoryContext:
    return RepositoryContext(
        repository_id="repo-a",
        repository="Owner/repo-a",
        control=root / "repo-a" / "control",
        work=root / "repo-a" / "work",
        checkpoints=root / "repo-a" / "checkpoints",
        agent_binding=BINDING,
    )


def task_node(node_id: str, depends_on: list[str]) -> dict:
    return {
        "id": node_id,
        "kind": "task",
        "repository_id": "repo-a",
        "agent_binding": BINDING,
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
        "created_at": "2026-09-19T15:30:00Z",
        "nodes": [
            task_node("audit", []),
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
        "workflow_id": WORKFLOW_ID,
        "revision": 1,
        "created_at": "2026-09-19T15:31:00Z",
        "parent_digest": contract.manifest_digest(base),
        "checkpoint_node_id": "review-audit",
        "nodes": [
            task_node("implement", ["review-audit"]),
            {
                "id": "review-implementation",
                "kind": "planner_checkpoint",
                "depends_on": ["implement"],
            },
        ],
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
            raise AssertionError("duplicate publication")
        self.tasks[key] = task
        self.publish_calls.append(key)

    def has_unrelated_work(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool:
        return False


class WorkflowLineageCancellationTests(unittest.TestCase):
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
        self.repo = repository(self.root)
        self.control = MemoryControlPlane()
        self.first = self._prepare_revision_one()

    def _prepare_revision_one(self) -> dict:
        for target in ("dispatched", "running", "succeeded"):
            self.workflow_store.set_node_state(WORKFLOW_ID, "audit", target)
        resolution = self.workflow_store.resolve_planner_checkpoint(
            WORKFLOW_ID,
            "review-audit",
            resolver="chatgpt-planner",
        )
        first = revision_one(self.base)
        self.revision_store.append(WORKFLOW_ID, first)
        base_states = dict(self.workflow_store.load_state(WORKFLOW_ID)["node_states"])
        self.activation_store.append(
            WORKFLOW_ID,
            1,
            base_states,
            resolution,
            activated_at="2026-09-19T15:32:00Z",
        )
        self.effective_store.initialize(WORKFLOW_ID)
        return first

    def tick(self) -> coordinator.TickResult:
        return lineage_coordinator.tick_lineage_workflow(
            self.effective_store,
            WORKFLOW_ID,
            [self.repo],
            self.control,
        )

    def test_cancel_before_dispatch_prevents_publication(self) -> None:
        cancelled = self.effective_store.cancel(WORKFLOW_ID)
        self.assertEqual(cancelled["node_states"]["implement"], "cancelled")

        tick = self.tick()
        self.assertEqual(tick.published, ())
        self.assertEqual(self.control.publish_calls, [])
        self.assertEqual(self.effective_store.load(WORKFLOW_ID)["workflow_state"], "cancelled")

    def test_cancel_running_child_reconciles_terminal_cancel_without_new_publish(self) -> None:
        first_tick = self.tick()
        self.assertEqual(first_tick.published, ("implement",))
        child = publishing.materialize_lineage_child_task(
            self.base,
            [self.first],
            "implement",
        )
        key = ("repo-a", str(child["id"]))
        self.control.kinds[key] = coordinator.ChildEvidenceKind.RUNNING
        self.tick()
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["node_states"]["implement"],
            "running",
        )

        cancelled = self.effective_store.cancel(WORKFLOW_ID)
        self.assertTrue(cancelled["cancel_requested"])
        self.assertEqual(cancelled["node_states"]["implement"], "running")
        self.assertEqual(cancelled["node_states"]["review-implementation"], "cancelled")
        self.assertEqual(len(self.control.publish_calls), 1)

        self.control.kinds[key] = coordinator.ChildEvidenceKind.CANCELLED
        terminal_tick = self.tick()
        self.assertEqual(terminal_tick.reconciled, ("implement",))
        final = self.effective_store.load(WORKFLOW_ID)
        self.assertEqual(final["node_states"]["implement"], "cancelled")
        self.assertEqual(final["workflow_state"], "cancelled")
        self.assertEqual(len(self.control.publish_calls), 1)


if __name__ == "__main__":
    unittest.main()
