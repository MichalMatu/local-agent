from __future__ import annotations

import copy
import unittest

from local_agent.workflow import contract, methods


BINDING = "00000000-0000-4000-8000-000000000051"


def task_node(node_id: str, phase: str, depends_on: list[str]) -> dict:
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


def deep_refactor_manifest() -> dict:
    audit = task_node("audit", "audit", [])
    checkpoint = {
        "id": "audit-review",
        "kind": "planner_checkpoint",
        "phase": "audit_checkpoint",
        "depends_on": ["audit"],
    }
    implementation = task_node(
        "implementation",
        "implementation",
        ["audit-review"],
    )
    focused = task_node(
        "focused",
        "focused_verification",
        ["implementation"],
    )
    full = task_node(
        "full",
        "full_verification",
        ["focused"],
    )
    full["task"].pop("commands")
    full["task"]["workflow_policy"] = "efficient-verification-v1"
    full["task"]["steps"] = [
        {
            "name": "prepare",
            "command": "true",
            "verification_level": "work",
        }
    ]
    full["task"]["verify_steps"] = [
        {
            "name": "full",
            "command": "true",
            "verification_level": "full",
        }
    ]
    review = task_node("review", "final_review", ["full"])
    spec = methods.load_builtin_method("deep-refactor")
    return {
        "schema_version": 1,
        "id": "deep-refactor-example",
        "created_at": "2026-09-19T12:06:00Z",
        "method": methods.method_reference(spec),
        "nodes": [audit, checkpoint, implementation, focused, full, review],
    }


class WorkflowMethodTests(unittest.TestCase):
    def test_builtin_catalog_has_initial_methods(self) -> None:
        specs = methods.list_builtin_methods()
        self.assertEqual(
            [spec["name"] for spec in specs],
            ["cross-repo-api-change", "deep-refactor", "release-candidate"],
        )
        for spec in specs:
            methods.validate_method_spec(spec)
            self.assertRegex(methods.method_digest(spec), r"^sha256:[0-9a-f]{64}$")

    def test_builtin_reference_is_digest_pinned(self) -> None:
        spec = methods.load_builtin_method("deep-refactor")
        reference = methods.method_reference(spec)
        methods.require_method_match(reference, spec)
        changed = copy.deepcopy(spec)
        changed["description"] += " changed"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            methods.require_method_match(reference, changed)

    def test_unknown_method_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown built-in workflow method"):
            methods.load_builtin_method("missing")

    def test_unknown_requirement_is_rejected(self) -> None:
        spec = methods.load_builtin_method("deep-refactor")
        spec["requirements"]["magic"] = True
        with self.assertRaisesRegex(ValueError, "unsupported method requirement"):
            methods.validate_method_spec(spec)

    def test_deep_refactor_manifest_satisfies_method(self) -> None:
        manifest = deep_refactor_manifest()
        contract.validate_workflow_manifest(manifest)
        spec = methods.load_builtin_method("deep-refactor")
        methods.validate_workflow_method(manifest, spec)

    def test_missing_required_phase_is_rejected_at_manifest_admission(self) -> None:
        manifest = deep_refactor_manifest()
        manifest["nodes"] = [
            node for node in manifest["nodes"] if node.get("phase") != "final_review"
        ]
        with self.assertRaisesRegex(ValueError, "missing required method phases"):
            contract.validate_workflow_manifest(manifest)

    def test_checkpoint_requirement_is_structural(self) -> None:
        manifest = deep_refactor_manifest()
        checkpoint = next(
            node for node in manifest["nodes"] if node["kind"] == "planner_checkpoint"
        )
        checkpoint["depends_on"] = ["focused"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            contract.validate_workflow_manifest(manifest)

        manifest = deep_refactor_manifest()
        manifest["nodes"] = [
            node for node in manifest["nodes"] if node["kind"] != "planner_checkpoint"
        ]
        implementation = next(
            node for node in manifest["nodes"] if node["id"] == "implementation"
        )
        implementation["depends_on"] = ["audit"]
        with self.assertRaisesRegex(ValueError, "planner checkpoint after audit"):
            contract.validate_workflow_manifest(manifest)

    def test_full_verification_requirement_uses_existing_policy(self) -> None:
        manifest = deep_refactor_manifest()
        full = next(
            node for node in manifest["nodes"] if node.get("phase") == "full_verification"
        )
        full["task"] = {
            "work_branch": "main",
            "allow_write": False,
            "resources": [],
            "commands": ["true"],
        }
        with self.assertRaisesRegex(ValueError, "efficient-verification-v1"):
            contract.validate_workflow_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
