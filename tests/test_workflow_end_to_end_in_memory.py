from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import coordinator, publishing
from local_agent.workflow.store import WorkflowStore


BINDING_A = "00000000-0000-4000-8000-000000000091"
BINDING_B = "00000000-0000-4000-8000-000000000092"
BINDING_C = "00000000-0000-4000-8000-000000000093"
WORKFLOW_ID = "three-repo-e2e"


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
    depends_on: list[str],
) -> dict:
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


def workflow_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": WORKFLOW_ID,
        "created_at": "2026-09-19T13:20:00Z",
        "nodes": [
            task_node("audit", "repo-a", BINDING_A, depends_on=[]),
            {
                "id": "review-audit",
                "kind": "planner_checkpoint",
                "depends_on": ["audit"],
            },
            task_node(
                "backend",
                "repo-a",
                BINDING_A,
                depends_on=["review-audit"],
            ),
            task_node(
                "android",
                "repo-b",
                BINDING_B,
                depends_on=["review-audit"],
            ),
            task_node(
                "firmware",
                "repo-c",
                BINDING_C,
                depends_on=["review-audit"],
            ),
            {
                "id": "integration-barrier",
                "kind": "barrier",
                "depends_on": ["backend", "android", "firmware"],
            },
            {
                "id": "release-choice",
                "kind": "user_gate",
                "depends_on": ["integration-barrier"],
                "prompt": "Ship the coordinated change?",
                "choices": ["ship", "hold"],
            },
            task_node(
                "release",
                "repo-a",
                BINDING_A,
                depends_on=["release-choice"],
            ),
        ],
    }


class MemoryControlPlane:
    def __init__(self) -> None:
        self.tasks: dict[tuple[str, str], dict] = {}
        self.kinds: dict[tuple[str, str], coordinator.ChildEvidenceKind] = {}
        self.publish_order: list[tuple[str, str]] = []

    def inspect_child(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_digest: str,
    ) -> coordinator.ChildEvidence:
        key = (repository.repository_id, task_id)
        task = self.tasks.get(key)
        if task is None:
            return coordinator.ChildEvidence(coordinator.ChildEvidenceKind.ABSENT)
        digest = task_digest(task)
        if digest != expected_digest:
            return coordinator.ChildEvidence(
                coordinator.ChildEvidenceKind.DIGEST_MISMATCH,
                task_digest=digest,
            )
        return coordinator.ChildEvidence(
            self.kinds.get(key, coordinator.ChildEvidenceKind.PENDING),
            task_digest=digest,
        )

    def publish_child(
        self,
        repository: RepositoryContext,
        task: dict,
    ) -> None:
        key = (repository.repository_id, str(task["id"]))
        if key in self.tasks:
            raise AssertionError("duplicate publication")
        self.tasks[key] = task
        self.publish_order.append(key)

    def has_unrelated_work(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool:
        return False

    def mark_succeeded(self, manifest: dict, node_id: str) -> None:
        task = publishing.materialize_child_task(manifest, node_id)
        repository_id = next(
            str(node["repository_id"])
            for node in manifest["nodes"]
            if node["id"] == node_id
        )
        key = (repository_id, str(task["id"]))
        if key not in self.tasks:
            raise AssertionError(f"child was not published: {node_id}")
        self.kinds[key] = coordinator.ChildEvidenceKind.SUCCEEDED


class WorkflowEndToEndInMemoryTests(unittest.TestCase):
    def test_three_repository_workflow_survives_waits_and_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / "state"
            repositories = [
                repository(root, "repo-a", BINDING_A),
                repository(root, "repo-b", BINDING_B),
                repository(root, "repo-c", BINDING_C),
            ]
            manifest = workflow_manifest()
            control = MemoryControlPlane()
            store = WorkflowStore(state_dir)
            store.submit(manifest)

            first = coordinator.tick_workflow(
                store,
                WORKFLOW_ID,
                repositories,
                control,
            )
            self.assertEqual(first.published, ("audit",))
            control.mark_succeeded(manifest, "audit")

            coordinator.tick_workflow(store, WORKFLOW_ID, repositories, control)
            checkpoint_state = store.load_state(WORKFLOW_ID)
            self.assertEqual(checkpoint_state["workflow_state"], "waiting_planner")
            self.assertEqual(
                checkpoint_state["node_states"]["review-audit"],
                "waiting_planner",
            )
            self.assertEqual(
                checkpoint_state["node_states"]["backend"],
                "blocked_dependency",
            )

            # Simulate a coordinator/service restart. Durable state must be sufficient
            # to continue; no process-local object is relied upon.
            store = WorkflowStore(state_dir)
            store.resolve_planner_checkpoint(
                WORKFLOW_ID,
                "review-audit",
                resolver="chatgpt-planner",
                note="Audit evidence reviewed; continue implementation.",
            )

            parallel = coordinator.tick_workflow(
                store,
                WORKFLOW_ID,
                repositories,
                control,
            )
            self.assertEqual(
                set(parallel.published),
                {"backend", "android", "firmware"},
            )

            for node_id in ("backend", "android", "firmware"):
                control.mark_succeeded(manifest, node_id)
            coordinator.tick_workflow(store, WORKFLOW_ID, repositories, control)

            gate_state = store.load_state(WORKFLOW_ID)
            self.assertEqual(
                gate_state["node_states"]["integration-barrier"],
                "succeeded",
            )
            self.assertEqual(
                gate_state["node_states"]["release-choice"],
                "waiting_user",
            )
            self.assertEqual(gate_state["workflow_state"], "waiting_user")

            store.resolve_user_gate(
                WORKFLOW_ID,
                "release-choice",
                "ship",
                resolver="local-operator",
            )
            release_tick = coordinator.tick_workflow(
                store,
                WORKFLOW_ID,
                repositories,
                control,
            )
            self.assertEqual(release_tick.published, ("release",))

            control.mark_succeeded(manifest, "release")
            coordinator.tick_workflow(store, WORKFLOW_ID, repositories, control)
            final_state = store.load_state(WORKFLOW_ID)
            self.assertEqual(final_state["workflow_state"], "completed")
            self.assertTrue(
                all(value == "succeeded" for value in final_state["node_states"].values())
            )
            self.assertEqual(
                final_state["planner_checkpoints"]["review-audit"]["resolver"],
                "chatgpt-planner",
            )
            self.assertEqual(
                final_state["gate_decisions"]["release-choice"]["decision"],
                "ship",
            )


if __name__ == "__main__":
    unittest.main()
