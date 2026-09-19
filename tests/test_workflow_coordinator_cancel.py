from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import coordinator, publishing
from local_agent.workflow.evidence import ChildEvidence, ChildEvidenceKind
from local_agent.workflow.store import WorkflowStore


BINDING = "00000000-0000-4000-8000-000000000081"


def manifest() -> dict:
    return {
        "schema_version": 1,
        "id": "cancel-reconcile",
        "created_at": "2026-09-19T12:50:00Z",
        "nodes": [
            {
                "id": "active",
                "kind": "task",
                "repository_id": "repo-a",
                "agent_binding": BINDING,
                "depends_on": [],
                "task": {
                    "work_branch": "main",
                    "allow_write": False,
                    "resources": [],
                    "commands": ["true"],
                },
            },
            {
                "id": "after",
                "kind": "task",
                "repository_id": "repo-a",
                "agent_binding": BINDING,
                "depends_on": ["active"],
                "task": {
                    "work_branch": "main",
                    "allow_write": False,
                    "resources": [],
                    "commands": ["true"],
                },
            },
        ],
    }


class CancelControlPlane:
    def __init__(self) -> None:
        self.tasks: dict[str, dict] = {}
        self.cancelled: set[str] = set()
        self.publish_calls = 0

    def inspect_child(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_digest: str,
    ) -> ChildEvidence:
        task = self.tasks.get(task_id)
        if task is None:
            return ChildEvidence(ChildEvidenceKind.ABSENT)
        actual = task_digest(task)
        if actual != expected_digest:
            return ChildEvidence(ChildEvidenceKind.DIGEST_MISMATCH, task_digest=actual)
        if task_id in self.cancelled:
            return ChildEvidence(
                ChildEvidenceKind.CANCELLED,
                task_digest=actual,
                failure_reason="cancelled_by_operator",
            )
        return ChildEvidence(ChildEvidenceKind.PENDING, task_digest=actual)

    def publish_child(self, repository: RepositoryContext, task: dict) -> None:
        self.publish_calls += 1
        self.tasks[str(task["id"])] = task

    def has_unrelated_work(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool:
        return False


class WorkflowCoordinatorCancellationTests(unittest.TestCase):
    def test_cancelled_child_becomes_terminal_cancelled_without_republication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = WorkflowStore(root / "state")
            workflow = manifest()
            store.submit(workflow)
            repository = RepositoryContext(
                repository_id="repo-a",
                repository="Owner/repo-a",
                control=root / "control",
                work=root / "work",
                checkpoints=root / "checkpoints",
                agent_binding=BINDING,
            )
            control = CancelControlPlane()

            first = coordinator.tick_workflow(
                store,
                workflow["id"],
                [repository],
                control,
            )
            self.assertEqual(first.published, ("active",))
            child = publishing.materialize_child_task(workflow, "active")
            control.cancelled.add(str(child["id"]))

            second = coordinator.tick_workflow(
                store,
                workflow["id"],
                [repository],
                control,
            )
            self.assertEqual(second.published, ())
            self.assertEqual(second.reconciled, ("active",))
            self.assertEqual(control.publish_calls, 1)

            current = store.load_state(workflow["id"])
            self.assertEqual(current["node_states"]["active"], "cancelled")
            self.assertEqual(current["node_states"]["after"], "blocked_dependency")
            self.assertEqual(current["workflow_state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
