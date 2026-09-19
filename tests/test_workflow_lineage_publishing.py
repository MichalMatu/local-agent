from __future__ import annotations

import copy
import unittest

from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import contract, publishing, revisions


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
        "id": "lineage-publishing",
        "created_at": "2026-09-19T14:50:00Z",
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
        "created_at": "2026-09-19T14:51:00Z",
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
        "created_at": "2026-09-19T14:52:00Z",
        "parent_digest": revisions.revision_digest(first),
        "checkpoint_node_id": "review-implementation",
        "nodes": [task_node("verify", ["review-implementation"])],
    }


class WorkflowLineagePublishingTests(unittest.TestCase):
    def test_base_child_payload_is_identical_with_or_without_revision_lineage(self) -> None:
        base = base_manifest()
        first = revision_one(base)
        static = publishing.materialize_child_task(base, "audit")
        lineage = publishing.materialize_lineage_child_task(base, [first], "audit")
        self.assertEqual(lineage, static)
        self.assertEqual(task_digest(lineage), task_digest(static))

    def test_revision_one_child_identity_does_not_change_when_revision_two_is_appended(self) -> None:
        base = base_manifest()
        first = revision_one(base)
        second = revision_two(base, first)
        before = publishing.materialize_lineage_child_task(base, [first], "implement")
        after = publishing.materialize_lineage_child_task(
            base,
            [first, second],
            "implement",
        )
        self.assertEqual(after, before)
        self.assertEqual(task_digest(after), task_digest(before))
        self.assertEqual(after["workflow"]["revision"], 1)
        self.assertEqual(
            after["workflow"]["revision_digest"],
            revisions.revision_digest(first),
        )

    def test_revision_two_child_is_pinned_to_revision_two_digest(self) -> None:
        base = base_manifest()
        first = revision_one(base)
        second = revision_two(base, first)
        child = publishing.materialize_lineage_child_task(
            base,
            [first, second],
            "verify",
        )
        self.assertEqual(child["workflow"]["revision"], 2)
        self.assertEqual(
            child["workflow"]["revision_digest"],
            revisions.revision_digest(second),
        )
        self.assertEqual(
            publishing.node_introduction_identity(base, [first, second], "verify"),
            (2, revisions.revision_digest(second)),
        )

    def test_modifying_revision_payload_changes_only_nodes_introduced_by_that_revision(self) -> None:
        base = base_manifest()
        first = revision_one(base)
        original = publishing.materialize_lineage_child_task(base, [first], "implement")
        changed = copy.deepcopy(first)
        changed["nodes"][0]["task"]["commands"] = ["printf changed"]
        changed_child = publishing.materialize_lineage_child_task(
            base,
            [changed],
            "implement",
        )
        self.assertNotEqual(changed_child["id"], original["id"])
        self.assertNotEqual(task_digest(changed_child), task_digest(original))
        self.assertEqual(
            publishing.materialize_lineage_child_task(base, [changed], "audit"),
            publishing.materialize_child_task(base, "audit"),
        )

    def test_unknown_node_identity_fails_closed(self) -> None:
        base = base_manifest()
        first = revision_one(base)
        with self.assertRaisesRegex(ValueError, "unknown workflow node"):
            publishing.materialize_lineage_child_task(base, [first], "missing")

    def test_child_task_id_requires_exact_lowercase_sha256(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity_digest"):
            publishing.child_task_id(
                "lineage-publishing",
                "implement",
                "sha256:" + "G" * 64,
            )


if __name__ == "__main__":
    unittest.main()
