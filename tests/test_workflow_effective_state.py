from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_agent.workflow import contract, revisions
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore


BINDING = "00000000-0000-4000-8000-000000000101"


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
        "id": "effective-state",
        "created_at": "2026-09-19T14:40:00Z",
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
        "created_at": "2026-09-19T14:41:00Z",
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


def revision_two(base: dict, first: dict) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": base["id"],
        "revision": 2,
        "created_at": "2026-09-19T14:42:00Z",
        "parent_digest": revisions.revision_digest(first),
        "checkpoint_node_id": "review-implementation",
        "nodes": [task_node("verify", ["review-implementation"])],
    }


class WorkflowEffectiveStateTests(unittest.TestCase):
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

    def prepare_first_activation(self) -> tuple[dict, dict]:
        self.workflow_store.set_node_state(self.base["id"], "audit", "dispatched")
        self.workflow_store.set_node_state(self.base["id"], "audit", "running")
        self.workflow_store.set_node_state(self.base["id"], "audit", "succeeded")
        resolution = self.workflow_store.resolve_planner_checkpoint(
            self.base["id"],
            "review-audit",
            resolver="chatgpt-planner",
            note="Audit accepted.",
        )
        first = revision_one(self.base)
        self.revision_store.append(self.base["id"], first)
        base_states = dict(self.workflow_store.load_state(self.base["id"])["node_states"])
        self.activation_store.append(
            self.base["id"],
            1,
            base_states,
            resolution,
            activated_at="2026-09-19T14:43:00Z",
        )
        return first, resolution

    def test_initialize_keeps_base_state_separate_and_adds_revision_nodes(self) -> None:
        self.prepare_first_activation()
        base_before = self.workflow_store.load_state(self.base["id"])
        effective = self.effective_store.initialize(self.base["id"])

        self.assertEqual(effective["active_revision"], 1)
        self.assertEqual(effective["node_states"]["audit"], "succeeded")
        self.assertEqual(effective["node_states"]["review-audit"], "succeeded")
        self.assertEqual(effective["node_states"]["implement"], "ready")
        self.assertEqual(
            effective["node_states"]["review-implementation"],
            "blocked_dependency",
        )
        self.assertEqual(self.workflow_store.load_state(self.base["id"]), base_before)

    def test_effective_task_progress_and_checkpoint_survive_restart(self) -> None:
        self.prepare_first_activation()
        self.effective_store.initialize(self.base["id"])
        self.effective_store.set_task_node_state(self.base["id"], "implement", "dispatched")
        self.effective_store.set_task_node_state(self.base["id"], "implement", "running")
        updated = self.effective_store.set_task_node_state(
            self.base["id"],
            "implement",
            "succeeded",
        )
        self.assertEqual(updated["node_states"]["review-implementation"], "waiting_planner")

        resolution = self.effective_store.resolve_planner_checkpoint(
            self.base["id"],
            "review-implementation",
            resolver="chatgpt-planner",
            note="Implementation reviewed.",
            resolved_at="2026-09-19T14:44:00Z",
        )
        self.assertEqual(resolution["node_id"], "review-implementation")

        restarted = WorkflowEffectiveStateStore(
            WorkflowStore(self.state_dir),
        )
        loaded = restarted.load(self.base["id"])
        self.assertEqual(loaded["node_states"]["implement"], "succeeded")
        self.assertEqual(loaded["node_states"]["review-implementation"], "succeeded")
        self.assertEqual(
            loaded["planner_checkpoints"]["review-implementation"]["resolver"],
            "chatgpt-planner",
        )

    def test_second_activation_pins_exact_effective_state_and_then_becomes_ready(self) -> None:
        first, _ = self.prepare_first_activation()
        self.effective_store.initialize(self.base["id"])
        for target in ("dispatched", "running", "succeeded"):
            self.effective_store.set_task_node_state(
                self.base["id"],
                "implement",
                target,
            )
        resolution = self.effective_store.resolve_planner_checkpoint(
            self.base["id"],
            "review-implementation",
            resolver="chatgpt-planner",
            resolved_at="2026-09-19T14:45:00Z",
        )
        current = self.effective_store.load(self.base["id"])
        second = revision_two(self.base, first)
        self.revision_store.append(self.base["id"], second)
        self.activation_store.append(
            self.base["id"],
            2,
            dict(current["node_states"]),
            resolution,
            activated_at="2026-09-19T14:45:01Z",
        )

        activated = self.effective_store.activate_next_revision(self.base["id"])
        self.assertEqual(activated["active_revision"], 2)
        self.assertEqual(activated["node_states"]["verify"], "ready")
        self.assertEqual(activated["node_states"]["implement"], "succeeded")
        self.assertEqual(
            activated["lineage_tip_digest"],
            revisions.revision_digest(second),
        )

    def test_next_activation_rejects_state_drift_after_activation_record_created(self) -> None:
        first, _ = self.prepare_first_activation()
        self.effective_store.initialize(self.base["id"])
        for target in ("dispatched", "running", "succeeded"):
            self.effective_store.set_task_node_state(self.base["id"], "implement", target)
        resolution = self.effective_store.resolve_planner_checkpoint(
            self.base["id"],
            "review-implementation",
            resolver="chatgpt-planner",
            resolved_at="2026-09-19T14:46:00Z",
        )
        current = self.effective_store.load(self.base["id"])
        second = revision_two(self.base, first)
        self.revision_store.append(self.base["id"], second)
        self.activation_store.append(
            self.base["id"],
            2,
            dict(current["node_states"]),
            resolution,
            activated_at="2026-09-19T14:46:01Z",
        )

        path = self.state_dir / "workflows" / self.base["id"] / "effective_state.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["node_states"]["implement"] = "failed"
        payload["workflow_state"] = "failed"
        path.write_text(json.dumps(payload), encoding="utf-8")
        # The altered file is structurally valid, but the pre-created activation pins
        # the exact state digest that existed when the planner authorized rev2.
        with self.assertRaisesRegex(ValueError, "prior state does not match"):
            self.effective_store.activate_next_revision(self.base["id"])

    def test_non_task_transition_is_rejected(self) -> None:
        self.prepare_first_activation()
        self.effective_store.initialize(self.base["id"])
        with self.assertRaisesRegex(ValueError, "is not a task"):
            self.effective_store.set_task_node_state(
                self.base["id"],
                "review-implementation",
                "succeeded",
            )


if __name__ == "__main__":
    unittest.main()
