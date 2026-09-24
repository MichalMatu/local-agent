from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.conversation import contract
from local_agent.conversation.store import WorkflowConversationStore
from local_agent.workflow import contract as workflow_contract
from local_agent.workflow import state as workflow_state
from local_agent.workflow.store import WorkflowStore


BINDING = "00000000-0000-4000-8000-000000000081"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"


def mixed_workflow() -> dict:
    return {
        "schema_version": 1,
        "id": "mixed-reasoning-workflow",
        "created_at": "2026-09-24T00:00:00Z",
        "nodes": [
            {
                "id": "prep",
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
                "id": "audit",
                "kind": "reasoning",
                "repository_id": "repo-a",
                "agent_binding": BINDING,
                "depends_on": ["prep"],
            },
            {
                "id": "parallel",
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
        ],
    }


def request_for(workflow: dict) -> dict:
    return {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": "child-audit-001",
        "workflow_id": workflow["id"],
        "workflow_node_id": "audit",
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": workflow_contract.manifest_digest(workflow),
        "parent_conversation_url": PARENT_URL,
        "created_at": "2026-09-24T00:01:00Z",
        "role": "verification",
        "repository_id": "repo-a",
        "agent_binding": BINDING,
        "repository_ref": "main",
        "repository_commit_sha": "a" * 40,
        "scope": {"summary": "Verify the bounded result.", "paths": ["local_agent"]},
        "context_refs": [],
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }


class ConversationAdmissionAuthorityTests(unittest.TestCase):
    def test_waiting_conversation_does_not_mask_independent_ready_task(self) -> None:
        workflow = mixed_workflow()
        states = workflow_state.initial_node_states(workflow)
        self.assertEqual(states["prep"], "ready")
        self.assertEqual(states["audit"], "blocked_dependency")
        self.assertEqual(states["parallel"], "ready")
        self.assertEqual(workflow_state.workflow_state(states), "running")

        states["prep"] = workflow_state.transition_node_state(states["prep"], "succeeded")
        states = workflow_state.advance_dependency_states(workflow, states)
        self.assertEqual(states["audit"], "waiting_conversation")
        self.assertEqual(states["parallel"], "ready")
        self.assertEqual(workflow_state.workflow_state(states), "running")

    def test_new_request_requires_reasoning_node_to_be_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_store = WorkflowStore(Path(tmp))
            workflow = mixed_workflow()
            workflow_store.submit(workflow)
            conversation_store = WorkflowConversationStore(workflow_store, workflow["id"])
            request = request_for(workflow)

            with self.assertRaisesRegex(ValueError, "must be waiting_conversation"):
                conversation_store.admit_request(request)

            workflow_store.set_node_state(workflow["id"], "prep", "succeeded")
            admitted = conversation_store.admit_request(request)
            self.assertEqual(admitted["state"], "requested")


if __name__ == "__main__":
    unittest.main()
