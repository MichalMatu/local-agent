from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import coordinator, publishing
from local_agent.workflow.store import WorkflowStore


BINDING_A = "00000000-0000-4000-8000-000000000061"
BINDING_B = "00000000-0000-4000-8000-000000000062"


def repository(root: Path, repository_id: str, binding: str) -> RepositoryContext:
    return RepositoryContext(
        repository_id=repository_id,
        repository=f"Owner/{repository_id}",
        control=root / repository_id / "control",
        work=root / repository_id / "work",
        checkpoints=root / repository_id / "checkpoints",
        agent_binding=binding,
    )


def task_node(
    node_id: str,
    repository_id: str,
    binding: str,
    *,
    depends_on: list[str] | None = None,
) -> dict:
    return {
        "id": node_id,
        "kind": "task",
        "repository_id": repository_id,
        "agent_binding": binding,
        "depends_on": depends_on or [],
        "task": {
            "work_branch": "main",
            "allow_write": False,
            "resources": [],
            "commands": ["true"],
        },
    }


def manifest(nodes: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "id": "coordinator-example",
        "created_at": "2026-09-19T12:30:00Z",
        "nodes": nodes,
    }


class FakeControlPlane:
    def __init__(self) -> None:
        self.tasks: dict[tuple[str, str], dict] = {}
        self.evidence: dict[tuple[str, str], coordinator.ChildEvidenceKind] = {}
        self.unrelated_busy: set[str] = set()
        self.publish_calls: list[tuple[str, str]] = []
        self.crash_after_publish = False

    def inspect_child(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_digest: str,
    ) -> coordinator.ChildEvidence:
        key = (repository.repository_id, task_id)
        task = self.tasks.get(key)
        kind = self.evidence.get(key)
        if task is None:
            return coordinator.ChildEvidence(coordinator.ChildEvidenceKind.ABSENT)
        actual_digest = task_digest(task)
        if actual_digest != expected_digest:
            return coordinator.ChildEvidence(
                coordinator.ChildEvidenceKind.DIGEST_MISMATCH,
                task_digest=actual_digest,
            )
        return coordinator.ChildEvidence(
            kind or coordinator.ChildEvidenceKind.PENDING,
            task_digest=actual_digest,
        )

    def publish_child(
        self,
        repository: RepositoryContext,
        task: dict,
    ) -> None:
        key = (repository.repository_id, str(task["id"]))
        self.publish_calls.append(key)
        if key in self.tasks:
            raise AssertionError("duplicate child publication")
        self.tasks[key] = task
        if self.crash_after_publish:
            self.crash_after_publish = False
            raise RuntimeError("simulated crash after remote publication")

    def has_unrelated_work(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool:
        return repository.repository_id in self.unrelated_busy


class WorkflowCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = WorkflowStore(self.root / "state")
        self.repo_a = repository(self.root, "repo-a", BINDING_A)
        self.repo_b = repository(self.root, "repo-b", BINDING_B)
        self.control = FakeControlPlane()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def submit(self, workflow: dict) -> None:
        self.store.submit(workflow)

    def tick(self, repositories: list[RepositoryContext] | None = None) -> coordinator.TickResult:
        return coordinator.tick_workflow(
            self.store,
            "coordinator-example",
            repositories or [self.repo_a, self.repo_b],
            self.control,
        )

    def test_parallel_ready_nodes_publish_once_to_different_repositories(self) -> None:
        workflow = manifest(
            [
                task_node("a", "repo-a", BINDING_A),
                task_node("b", "repo-b", BINDING_B),
            ]
        )
        self.submit(workflow)
        result = self.tick()
        self.assertEqual(set(result.published), {"a", "b"})
        state = self.store.load_state(workflow["id"])
        self.assertEqual(state["node_states"]["a"], "dispatched")
        self.assertEqual(state["node_states"]["b"], "dispatched")
        self.assertEqual(len(self.control.publish_calls), 2)

    def test_same_repository_ready_nodes_are_serialized_by_coordinator(self) -> None:
        workflow = manifest(
            [
                task_node("a", "repo-a", BINDING_A),
                task_node("b", "repo-a", BINDING_A),
            ]
        )
        self.submit(workflow)
        result = self.tick([self.repo_a])
        self.assertEqual(result.published, ("a",))
        self.assertEqual(result.deferred_same_repository, ("b",))
        state = self.store.load_state(workflow["id"])
        self.assertEqual(state["node_states"]["a"], "dispatched")
        self.assertEqual(state["node_states"]["b"], "ready")

    def test_unrelated_repository_work_yields_without_publication(self) -> None:
        workflow = manifest([task_node("a", "repo-a", BINDING_A)])
        self.submit(workflow)
        self.control.unrelated_busy.add("repo-a")
        result = self.tick([self.repo_a])
        self.assertEqual(result.published, ())
        self.assertEqual(result.deferred_unrelated_work, ("a",))
        self.assertEqual(self.control.publish_calls, [])
        self.assertEqual(self.store.load_state(workflow["id"])["node_states"]["a"], "ready")

    def test_crash_after_publication_is_recovered_without_duplicate_publish(self) -> None:
        workflow = manifest([task_node("a", "repo-a", BINDING_A)])
        self.submit(workflow)
        self.control.crash_after_publish = True
        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            self.tick([self.repo_a])
        self.assertEqual(self.store.load_state(workflow["id"])["node_states"]["a"], "ready")
        self.assertEqual(len(self.control.publish_calls), 1)

        recovered = self.tick([self.repo_a])
        self.assertEqual(recovered.reconciled, ("a",))
        self.assertEqual(len(self.control.publish_calls), 1)
        self.assertEqual(self.store.load_state(workflow["id"])["node_states"]["a"], "dispatched")

    def test_pending_running_and_success_evidence_reconcile_exact_child(self) -> None:
        workflow = manifest([task_node("a", "repo-a", BINDING_A)])
        self.submit(workflow)
        self.tick([self.repo_a])
        task = publishing.materialize_child_task(workflow, "a")
        key = ("repo-a", task["id"])

        self.control.evidence[key] = coordinator.ChildEvidenceKind.RUNNING
        self.tick([self.repo_a])
        self.assertEqual(self.store.load_state(workflow["id"])["node_states"]["a"], "running")

        self.control.evidence[key] = coordinator.ChildEvidenceKind.SUCCEEDED
        self.tick([self.repo_a])
        state = self.store.load_state(workflow["id"])
        self.assertEqual(state["node_states"]["a"], "succeeded")
        self.assertEqual(state["workflow_state"], "completed")

    def test_terminal_failure_blocks_downstream_and_stops_new_dispatch(self) -> None:
        workflow = manifest(
            [
                task_node("a", "repo-a", BINDING_A),
                task_node("after", "repo-b", BINDING_B, depends_on=["a"]),
            ]
        )
        self.submit(workflow)
        self.tick()
        task = publishing.materialize_child_task(workflow, "a")
        key = ("repo-a", task["id"])
        self.control.evidence[key] = coordinator.ChildEvidenceKind.FAILED

        result = self.tick()
        self.assertEqual(result.published, ())
        state = self.store.load_state(workflow["id"])
        self.assertEqual(state["node_states"]["a"], "failed")
        self.assertEqual(state["node_states"]["after"], "blocked_dependency")
        self.assertEqual(state["workflow_state"], "failed")

    def test_interrupted_child_waits_for_planner_and_is_never_republished(self) -> None:
        workflow = manifest([task_node("a", "repo-a", BINDING_A)])
        self.submit(workflow)
        self.tick([self.repo_a])
        task = publishing.materialize_child_task(workflow, "a")
        key = ("repo-a", task["id"])
        self.control.evidence[key] = coordinator.ChildEvidenceKind.INTERRUPTED

        result = self.tick([self.repo_a])
        self.assertEqual(result.published, ())
        state = self.store.load_state(workflow["id"])
        self.assertEqual(state["node_states"]["a"], "blocked_interrupted")
        self.assertEqual(state["workflow_state"], "waiting_planner")
        self.assertEqual(len(self.control.publish_calls), 1)

    def test_digest_mismatch_fails_closed_without_republication(self) -> None:
        workflow = manifest([task_node("a", "repo-a", BINDING_A)])
        self.submit(workflow)
        expected = publishing.materialize_child_task(workflow, "a")
        conflicting = dict(expected)
        conflicting["commands"] = ["false"]
        key = ("repo-a", expected["id"])
        self.control.tasks[key] = conflicting

        result = self.tick([self.repo_a])
        self.assertEqual(result.integrity_failures, ("a",))
        self.assertEqual(self.control.publish_calls, [])
        self.assertEqual(self.store.load_state(workflow["id"])["node_states"]["a"], "failed")

    def test_missing_child_after_dispatched_state_is_integrity_error(self) -> None:
        workflow = manifest([task_node("a", "repo-a", BINDING_A)])
        self.submit(workflow)
        self.store.set_node_state(workflow["id"], "a", "dispatched")
        with self.assertRaisesRegex(coordinator.WorkflowIntegrityError, "missing after dispatch"):
            self.tick([self.repo_a])
        self.assertEqual(self.control.publish_calls, [])

    def test_exact_repository_binding_is_required_before_inspection(self) -> None:
        workflow = manifest([task_node("a", "repo-a", BINDING_A)])
        self.submit(workflow)
        wrong = repository(self.root, "repo-a", BINDING_B)
        with self.assertRaisesRegex(coordinator.WorkflowIntegrityError, "binding mismatch"):
            self.tick([wrong])
        self.assertEqual(self.control.publish_calls, [])

    def test_cancelled_workflow_never_dispatches_new_child(self) -> None:
        workflow = manifest([task_node("a", "repo-a", BINDING_A)])
        self.submit(workflow)
        self.store.cancel(workflow["id"])
        result = self.tick([self.repo_a])
        self.assertEqual(result.published, ())
        self.assertEqual(self.control.publish_calls, [])


if __name__ == "__main__":
    unittest.main()
