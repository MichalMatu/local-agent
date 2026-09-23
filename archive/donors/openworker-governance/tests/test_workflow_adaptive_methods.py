from __future__ import annotations

import copy
import unittest

from local_agent.workflow import contract, methods, revisions


BINDING = "00000000-0000-4000-8000-0000000000c1"


def task_node(
    node_id: str,
    phase: str,
    depends_on: list[str],
) -> dict:
    return {
        "id": node_id,
        "kind": "task",
        "phase": phase,
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


def full_verification_node(depends_on: list[str]) -> dict:
    node = task_node("full", "full_verification", depends_on)
    node["task"].pop("commands")
    node["task"]["workflow_policy"] = "efficient-verification-v1"
    node["task"]["steps"] = [
        {
            "name": "prepare",
            "command": "true",
            "verification_level": "work",
        }
    ]
    node["task"]["verify_steps"] = [
        {
            "name": "full",
            "command": "true",
            "verification_level": "full",
        }
    ]
    return node


def adaptive_base() -> dict:
    spec = methods.load_builtin_method("deep-refactor")
    return {
        "schema_version": 1,
        "id": "adaptive-method",
        "created_at": "2026-09-19T13:50:00Z",
        "method": methods.method_reference(spec),
        "method_mode": "adaptive",
        "nodes": [
            task_node("audit", "audit", []),
            {
                "id": "audit-review",
                "kind": "planner_checkpoint",
                "phase": "audit_checkpoint",
                "depends_on": ["audit"],
            },
        ],
    }


def completion_revision(base: dict) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": base["id"],
        "revision": 1,
        "created_at": "2026-09-19T13:55:00Z",
        "parent_digest": contract.manifest_digest(base),
        "checkpoint_node_id": "audit-review",
        "nodes": [
            task_node("implementation", "implementation", ["audit-review"]),
            task_node("focused", "focused_verification", ["implementation"]),
            full_verification_node(["focused"]),
            task_node("final-review", "final_review", ["full"]),
        ],
    }


class WorkflowAdaptiveMethodTests(unittest.TestCase):
    def test_adaptive_base_can_admit_incomplete_future_phases(self) -> None:
        base = adaptive_base()
        contract.validate_workflow_manifest(base)
        self.assertRegex(contract.manifest_digest(base), r"^sha256:[0-9a-f]{64}$")
        with self.assertRaisesRegex(ValueError, "missing required method phases"):
            contract.validate_complete_workflow_manifest(base)

    def test_static_mode_preserves_existing_fail_closed_method_admission(self) -> None:
        base = adaptive_base()
        base.pop("method_mode")
        with self.assertRaisesRegex(ValueError, "missing required method phases"):
            contract.validate_workflow_manifest(base)

    def test_adaptive_mode_requires_first_method_phase(self) -> None:
        base = adaptive_base()
        base["nodes"][0]["phase"] = "implementation"
        with self.assertRaisesRegex(ValueError, "first required method phase"):
            contract.validate_workflow_manifest(base)

    def test_method_mode_without_method_reference_is_rejected(self) -> None:
        base = adaptive_base()
        base.pop("method")
        with self.assertRaisesRegex(ValueError, "method_mode requires"):
            contract.validate_workflow_manifest(base)

    def test_adaptive_full_verification_is_checked_as_soon_as_it_appears(self) -> None:
        base = adaptive_base()
        bad_full = task_node("full", "full_verification", ["audit-review"])
        base["nodes"].append(bad_full)
        with self.assertRaisesRegex(ValueError, "efficient-verification-v1"):
            contract.validate_workflow_manifest(base)

    def test_complete_method_can_span_base_and_revision(self) -> None:
        base = adaptive_base()
        revision = completion_revision(base)
        revisions.validate_revision_sequence(base, [revision])
        effective = revisions.validate_effective_method_complete(base, [revision])
        self.assertEqual(effective["method_mode"], "adaptive")
        self.assertEqual(effective["nodes"][-1]["phase"], "final_review")

    def test_incomplete_revision_chain_is_valid_but_not_method_complete(self) -> None:
        base = adaptive_base()
        revision = completion_revision(base)
        revision["nodes"] = [
            node
            for node in revision["nodes"]
            if node.get("phase") != "final_review"
        ]
        revisions.validate_revision_sequence(base, [revision])
        with self.assertRaisesRegex(ValueError, "missing required method phases"):
            revisions.validate_effective_method_complete(base, [revision])

    def test_method_identity_remains_digest_pinned_across_adaptive_lineage(self) -> None:
        base = adaptive_base()
        changed = copy.deepcopy(base)
        changed["method"]["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            contract.validate_workflow_manifest(changed)


if __name__ == "__main__":
    unittest.main()
