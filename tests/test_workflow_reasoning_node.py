from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.repository.context import RepositoryContext
from local_agent.workflow import contract, coordinator, state
from local_agent.workflow.store import WorkflowStore


BINDING = "00000000-0000-4000-8000-000000000071"


def reasoning_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": "reasoning-workflow",
        "created_at": "2026-09-24T00:00:00Z",
        "nodes": [
            {
                "id": "audit",
                "kind": "reasoning",
                "repository_id": "repo-a",
                "agent_binding": BINDING,
                "depends_on": [],
            }
        ],
    }


class RejectingControlPlane:
    def inspect_child(self, *args, **kwargs):
        raise AssertionError("reasoning nodes must not be inspected as execution tasks")

    def publish_child(self, *args, **kwargs):
        raise AssertionError("reasoning nodes must not be published as execution tasks")

    def has_unrelated_work(self, *args, **kwargs):
        raise AssertionError("reasoning nodes must not enter execution scheduling")


class WorkflowReasoningNodeTests(unittest.TestCase):
    def test_reasoning_node_is_first_class_but_has_no_task_payload(self) -> None:
        manifest = reasoning_manifest()
        contract.validate_workflow_manifest(manifest)
        self.assertRegex(contract.manifest_digest(manifest), r"^sha256:[0-9a-f]{64}$")

        invalid = reasoning_manifest()
        invalid["nodes"][0]["task"] = {
            "work_branch": "main",
            "allow_write": False,
            "resources": [],
            "commands": ["true"],
        }
        with self.assertRaisesRegex(ValueError, "reasoning node .* unsupported fields"):
            contract.validate_workflow_manifest(invalid)

    def test_reasoning_node_waits_for_conversation_and_can_complete(self) -> None:
        manifest = reasoning_manifest()
        states = state.initial_node_states(manifest)
        self.assertEqual(states, {"audit": "waiting_conversation"})
        self.assertEqual(state.workflow_state(states), "waiting_conversation")

        states["audit"] = state.transition_node_state(
            states["audit"],
            "succeeded",
        )
        self.assertEqual(state.workflow_state(states), "completed")

    def test_execution_coordinator_never_publishes_reasoning_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = WorkflowStore(root / "state")
            manifest = reasoning_manifest()
            store.submit(manifest)
            repository = RepositoryContext(
                repository_id="repo-a",
                repository="Owner/repo-a",
                control=root / "repo-a" / "control",
                work=root / "repo-a" / "work",
                checkpoints=root / "repo-a" / "checkpoints",
                agent_binding=BINDING,
            )

            result = coordinator.tick_workflow(
                store,
                manifest["id"],
                [repository],
                RejectingControlPlane(),
            )

            self.assertEqual(result.published, ())
            persisted = store.load_state(manifest["id"])
            self.assertEqual(persisted["node_states"]["audit"], "waiting_conversation")
            self.assertEqual(persisted["workflow_state"], "waiting_conversation")


if __name__ == "__main__":
    unittest.main()
