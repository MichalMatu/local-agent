from __future__ import annotations

import unittest

from local_agent.workflow import continuation, contract, revisions


BINDING = "00000000-0000-4000-8000-0000000000e1"


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
        "id": "continuation-projection",
        "created_at": "2026-09-19T14:10:00Z",
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
        "created_at": "2026-09-19T14:11:00Z",
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


class WorkflowContinuationTests(unittest.TestCase):
    def test_succeeded_checkpoint_unlocks_only_new_revision_nodes(self) -> None:
        base = base_manifest()
        revision = revision_one(base)
        current = {"audit": "succeeded", "review": "succeeded"}
        projected = continuation.project_next_revision_states(
            base,
            [],
            revision,
            current,
        )
        self.assertEqual(projected["audit"], "succeeded")
        self.assertEqual(projected["review"], "succeeded")
        self.assertEqual(projected["implement"], "ready")
        self.assertEqual(projected["implementation-review"], "blocked_dependency")

    def test_unresolved_checkpoint_cannot_activate_revision(self) -> None:
        base = base_manifest()
        revision = revision_one(base)
        current = {"audit": "succeeded", "review": "waiting_planner"}
        with self.assertRaisesRegex(ValueError, "must be succeeded"):
            continuation.project_next_revision_states(base, [], revision, current)

    def test_current_state_keys_must_match_exact_prior_effective_graph(self) -> None:
        base = base_manifest()
        revision = revision_one(base)
        with self.assertRaisesRegex(ValueError, "do not match prior graph"):
            continuation.project_next_revision_states(
                base,
                [],
                revision,
                {"audit": "succeeded"},
            )

    def test_prior_state_must_already_be_dependency_normalized(self) -> None:
        base = base_manifest()
        revision = revision_one(base)
        current = {"audit": "succeeded", "review": "blocked_dependency"}
        with self.assertRaisesRegex(ValueError, "not dependency-normalized"):
            continuation.project_next_revision_states(base, [], revision, current)

    def test_second_revision_can_activate_after_revision_checkpoint_succeeds(self) -> None:
        base = base_manifest()
        first = revision_one(base)
        first_states = continuation.project_next_revision_states(
            base,
            [],
            first,
            {"audit": "succeeded", "review": "succeeded"},
        )
        first_states["implement"] = "succeeded"
        first_states["implementation-review"] = "succeeded"
        second = {
            "schema_version": 1,
            "workflow_id": base["id"],
            "revision": 2,
            "created_at": "2026-09-19T14:12:00Z",
            "parent_digest": revisions.revision_digest(first),
            "checkpoint_node_id": "implementation-review",
            "nodes": [task_node("verify", ["implementation-review"])],
        }
        projected = continuation.project_next_revision_states(
            base,
            [first],
            second,
            first_states,
        )
        self.assertEqual(projected["verify"], "ready")
        self.assertEqual(projected["audit"], "succeeded")
        self.assertEqual(projected["implementation-review"], "succeeded")


if __name__ == "__main__":
    unittest.main()
