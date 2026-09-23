from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from local_agent.workflow import contract, revisions
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore


BINDING = "00000000-0000-4000-8000-0000000000f1"


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
        "id": "activation-ledger",
        "created_at": "2026-09-19T14:20:00Z",
        "nodes": [
            task_node("audit", []),
            {
                "id": "review",
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
        "created_at": "2026-09-19T14:21:00Z",
        "parent_digest": contract.manifest_digest(base),
        "checkpoint_node_id": "review",
        "nodes": [
            task_node("implement", ["review"]),
            {
                "id": "implementation-review",
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
        "created_at": "2026-09-19T14:22:00Z",
        "parent_digest": revisions.revision_digest(first),
        "checkpoint_node_id": "implementation-review",
        "nodes": [task_node("verify", ["implementation-review"])],
    }


def synthetic_resolution(workflow_id: str, node_id: str, timestamp: str) -> dict:
    return {
        "workflow_id": workflow_id,
        "node_id": node_id,
        "resolver": "chatgpt-planner",
        "resolved_at": timestamp,
    }


class WorkflowActivationTests(unittest.TestCase):
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

    def resolve_base_checkpoint(self) -> tuple[dict, dict[str, str]]:
        self.workflow_store.set_node_state(self.base["id"], "audit", "dispatched")
        self.workflow_store.set_node_state(self.base["id"], "audit", "running")
        self.workflow_store.set_node_state(self.base["id"], "audit", "succeeded")
        resolution = self.workflow_store.resolve_planner_checkpoint(
            self.base["id"],
            "review",
            resolver="chatgpt-planner",
            note="Continue with implementation.",
        )
        states = dict(self.workflow_store.load_state(self.base["id"])["node_states"])
        return resolution, states

    def test_first_activation_pins_revision_resolution_prior_state_and_projection(self) -> None:
        first = revision_one(self.base)
        self.revision_store.append(self.base["id"], first)
        resolution, states = self.resolve_base_checkpoint()
        record = self.activation_store.append(
            self.base["id"],
            1,
            states,
            resolution,
            activated_at="2026-09-19T14:23:00Z",
        )
        self.assertEqual(record["revision"], 1)
        self.assertEqual(record["revision_digest"], revisions.revision_digest(first))
        self.assertEqual(record["checkpoint_node_id"], "review")
        self.assertEqual(
            record["new_node_states"],
            {"implement": "ready", "implementation-review": "blocked_dependency"},
        )
        self.assertRegex(record["checkpoint_resolution_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(record["prior_state_digest"], r"^sha256:[0-9a-f]{64}$")

    def test_activation_survives_restart_and_identical_retry_is_idempotent(self) -> None:
        first = revision_one(self.base)
        self.revision_store.append(self.base["id"], first)
        resolution, states = self.resolve_base_checkpoint()
        first_record = self.activation_store.append(
            self.base["id"],
            1,
            states,
            resolution,
            activated_at="2026-09-19T14:24:00Z",
        )

        restarted_workflow = WorkflowStore(self.state_dir)
        restarted_revisions = WorkflowRevisionStore(restarted_workflow)
        restarted = WorkflowRevisionActivationStore(
            restarted_workflow,
            restarted_revisions,
        )
        self.assertEqual(restarted.load(self.base["id"]), [first_record])
        retried = restarted.append(
            self.base["id"],
            1,
            states,
            resolution,
        )
        self.assertEqual(retried, first_record)

    def test_conflicting_retry_provenance_is_rejected(self) -> None:
        first = revision_one(self.base)
        self.revision_store.append(self.base["id"], first)
        resolution, states = self.resolve_base_checkpoint()
        self.activation_store.append(
            self.base["id"],
            1,
            states,
            resolution,
            activated_at="2026-09-19T14:25:00Z",
        )
        conflicting = copy.deepcopy(resolution)
        conflicting["resolver"] = "different-planner"
        with self.assertRaisesRegex(ValueError, "different provenance"):
            self.activation_store.append(
                self.base["id"],
                1,
                states,
                conflicting,
            )

    def test_unresolved_checkpoint_cannot_create_activation(self) -> None:
        first = revision_one(self.base)
        self.revision_store.append(self.base["id"], first)
        self.workflow_store.set_node_state(self.base["id"], "audit", "dispatched")
        self.workflow_store.set_node_state(self.base["id"], "audit", "running")
        self.workflow_store.set_node_state(self.base["id"], "audit", "succeeded")
        states = dict(self.workflow_store.load_state(self.base["id"])["node_states"])
        with self.assertRaisesRegex(ValueError, "must be succeeded"):
            self.activation_store.append(
                self.base["id"],
                1,
                states,
                synthetic_resolution(
                    self.base["id"],
                    "review",
                    "2026-09-19T14:26:00Z",
                ),
            )

    def test_second_activation_can_use_prior_effective_state_without_mutating_base_state(self) -> None:
        first = revision_one(self.base)
        second = revision_two(self.base, first)
        self.revision_store.append(self.base["id"], first)
        self.revision_store.append(self.base["id"], second)
        resolution, base_states = self.resolve_base_checkpoint()
        first_record = self.activation_store.append(
            self.base["id"],
            1,
            base_states,
            resolution,
            activated_at="2026-09-19T14:27:00Z",
        )
        effective_states = dict(base_states)
        effective_states.update(first_record["new_node_states"])
        effective_states["implement"] = "succeeded"
        effective_states["implementation-review"] = "succeeded"
        second_record = self.activation_store.append(
            self.base["id"],
            2,
            effective_states,
            synthetic_resolution(
                self.base["id"],
                "implementation-review",
                "2026-09-19T14:28:00Z",
            ),
            activated_at="2026-09-19T14:28:01Z",
        )
        self.assertEqual(second_record["new_node_states"], {"verify": "ready"})
        self.assertEqual(
            self.workflow_store.load_state(self.base["id"])["node_states"],
            base_states,
        )

    def test_tampered_activation_revision_digest_is_rejected_on_reload(self) -> None:
        first = revision_one(self.base)
        self.revision_store.append(self.base["id"], first)
        resolution, states = self.resolve_base_checkpoint()
        self.activation_store.append(
            self.base["id"],
            1,
            states,
            resolution,
            activated_at="2026-09-19T14:29:00Z",
        )
        path = (
            self.state_dir
            / "workflows"
            / self.base["id"]
            / "activations"
            / "000001.json"
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["revision_digest"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "revision digest mismatch"):
            self.activation_store.load(self.base["id"])


if __name__ == "__main__":
    unittest.main()
