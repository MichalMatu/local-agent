from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.workflow import contract
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore


BINDING = "00000000-0000-4000-8000-000000000111"


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
        "id": "effective-controls",
        "created_at": "2026-09-19T15:20:00Z",
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
        "workflow_id": base["id"],
        "revision": 1,
        "created_at": "2026-09-19T15:21:00Z",
        "parent_digest": contract.manifest_digest(base),
        "checkpoint_node_id": "review-audit",
        "nodes": [
            task_node("implement", ["review-audit"]),
            {
                "id": "approve-release",
                "kind": "user_gate",
                "depends_on": ["implement"],
                "prompt": "Release the verified change?",
                "choices": ["approve", "reject"],
            },
            task_node("release", ["approve-release"]),
        ],
    }


class WorkflowEffectiveControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_dir = Path(self.tmp.name) / "state"
        self.workflow_store = WorkflowStore(self.state_dir)
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
        self._initialize_revision_one()

    def _initialize_revision_one(self) -> None:
        for target in ("dispatched", "running", "succeeded"):
            self.workflow_store.set_node_state(self.base["id"], "audit", target)
        resolution = self.workflow_store.resolve_planner_checkpoint(
            self.base["id"],
            "review-audit",
            resolver="chatgpt-planner",
            note="Audit accepted.",
        )
        revision = revision_one(self.base)
        self.revision_store.append(self.base["id"], revision)
        base_states = dict(self.workflow_store.load_state(self.base["id"])["node_states"])
        self.activation_store.append(
            self.base["id"],
            1,
            base_states,
            resolution,
            activated_at="2026-09-19T15:22:00Z",
        )
        self.effective_store.initialize(self.base["id"])

    def _complete_implementation(self) -> None:
        for target in ("dispatched", "running", "succeeded"):
            self.effective_store.set_task_node_state(
                self.base["id"],
                "implement",
                target,
            )

    def test_user_gate_resolution_is_durable_exact_once_and_unlocks_release(self) -> None:
        self._complete_implementation()
        waiting = self.effective_store.load(self.base["id"])
        self.assertEqual(waiting["node_states"]["approve-release"], "waiting_user")
        self.assertEqual(waiting["node_states"]["release"], "blocked_dependency")

        decision = self.effective_store.resolve_user_gate(
            self.base["id"],
            "approve-release",
            "approve",
            resolver="local-operator",
            decided_at="2026-09-19T15:23:00Z",
        )
        self.assertEqual(decision["decision"], "approve")
        self.assertEqual(decision["resolver"], "local-operator")
        resolved = self.effective_store.load(self.base["id"])
        self.assertEqual(resolved["node_states"]["approve-release"], "succeeded")
        self.assertEqual(resolved["node_states"]["release"], "ready")

        restarted = WorkflowEffectiveStateStore(WorkflowStore(self.state_dir))
        self.assertEqual(
            restarted.load(self.base["id"])["gate_decisions"]["approve-release"],
            decision,
        )
        self.assertEqual(
            restarted.resolve_user_gate(
                self.base["id"],
                "approve-release",
                "approve",
                resolver="another-resolver",
            ),
            decision,
        )
        with self.assertRaisesRegex(ValueError, "already resolved as"):
            restarted.resolve_user_gate(
                self.base["id"],
                "approve-release",
                "reject",
                resolver="another-resolver",
            )

    def test_user_gate_rejects_invalid_choice_and_non_gate_node(self) -> None:
        self._complete_implementation()
        with self.assertRaisesRegex(ValueError, "not an allowed choice"):
            self.effective_store.resolve_user_gate(
                self.base["id"],
                "approve-release",
                "maybe",
                resolver="local-operator",
            )
        with self.assertRaisesRegex(ValueError, "is not a user gate"):
            self.effective_store.resolve_user_gate(
                self.base["id"],
                "implement",
                "approve",
                resolver="local-operator",
            )

    def test_cancel_preserves_running_child_and_cancels_unstarted_nodes(self) -> None:
        self.effective_store.set_task_node_state(
            self.base["id"],
            "implement",
            "dispatched",
        )
        self.effective_store.set_task_node_state(
            self.base["id"],
            "implement",
            "running",
        )

        cancelled = self.effective_store.cancel(self.base["id"])
        self.assertTrue(cancelled["cancel_requested"])
        self.assertEqual(cancelled["node_states"]["implement"], "running")
        self.assertEqual(cancelled["node_states"]["approve-release"], "cancelled")
        self.assertEqual(cancelled["node_states"]["release"], "cancelled")
        self.assertEqual(cancelled["workflow_state"], "running")

        repeated = self.effective_store.cancel(self.base["id"])
        self.assertEqual(repeated, cancelled)

        terminal = self.effective_store.set_task_node_state(
            self.base["id"],
            "implement",
            "cancelled",
        )
        self.assertEqual(terminal["workflow_state"], "cancelled")

    def test_cancel_before_dispatch_makes_workflow_terminal_without_touching_base_state(self) -> None:
        base_before = self.workflow_store.load_state(self.base["id"])
        cancelled = self.effective_store.cancel(self.base["id"])
        self.assertTrue(cancelled["cancel_requested"])
        self.assertEqual(cancelled["workflow_state"], "cancelled")
        self.assertEqual(cancelled["node_states"]["implement"], "cancelled")
        self.assertEqual(self.workflow_store.load_state(self.base["id"]), base_before)


if __name__ == "__main__":
    unittest.main()
