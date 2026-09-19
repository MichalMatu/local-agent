from __future__ import annotations

import copy
import unittest

from local_agent.workflow import contract, methods


BINDING_A = "00000000-0000-4000-8000-000000000201"
BINDING_B = "00000000-0000-4000-8000-000000000202"


def task_node(
    node_id: str,
    phase: str,
    repository_id: str,
    binding: str,
    depends_on: list[str],
) -> dict:
    return {
        "id": node_id,
        "kind": "task",
        "phase": phase,
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


def cross_repo_manifest() -> dict:
    spec = methods.load_builtin_method("cross-repo-api-change")
    return {
        "schema_version": 1,
        "id": "cross-repo-method-v2",
        "created_at": "2026-09-19T16:20:00Z",
        "method": methods.method_reference(spec),
        "nodes": [
            task_node("contract", "contract", "repo-a", BINDING_A, []),
            task_node(
                "implement-a",
                "implementation",
                "repo-a",
                BINDING_A,
                ["contract"],
            ),
            task_node(
                "implement-b",
                "implementation",
                "repo-b",
                BINDING_B,
                ["contract"],
            ),
            {
                "id": "implementation-join",
                "kind": "barrier",
                "phase": "implementation_join",
                "depends_on": ["implement-a", "implement-b"],
            },
            task_node(
                "integration",
                "integration",
                "repo-a",
                BINDING_A,
                ["implementation-join"],
            ),
            task_node(
                "final-review",
                "final_review",
                "repo-a",
                BINDING_A,
                ["integration"],
            ),
        ],
    }


class WorkflowCrossRepoMethodTests(unittest.TestCase):
    def test_builtin_cross_repo_method_is_v2_and_enforces_topology(self) -> None:
        spec = methods.load_builtin_method("cross-repo-api-change")
        self.assertEqual(spec["version"], 2)
        self.assertTrue(spec["requirements"]["multi_repository_implementation"])
        self.assertTrue(spec["requirements"]["integration_joins_implementation"])
        self.assertTrue(spec["requirements"]["final_review_after_integration"])

        manifest = cross_repo_manifest()
        contract.validate_workflow_manifest(manifest)
        methods.validate_workflow_method(manifest, spec)

    def test_implementation_must_span_at_least_two_repositories(self) -> None:
        manifest = cross_repo_manifest()
        implement_b = next(node for node in manifest["nodes"] if node["id"] == "implement-b")
        implement_b["repository_id"] = "repo-a"
        implement_b["agent_binding"] = BINDING_A

        with self.assertRaisesRegex(ValueError, "at least two repositories"):
            contract.validate_workflow_manifest(manifest)

    def test_integration_must_join_every_implementation_task(self) -> None:
        manifest = cross_repo_manifest()
        integration = next(node for node in manifest["nodes"] if node["id"] == "integration")
        integration["depends_on"] = ["implement-a"]

        with self.assertRaisesRegex(ValueError, "all implementation tasks"):
            contract.validate_workflow_manifest(manifest)

    def test_transitive_barrier_join_satisfies_integration_requirement(self) -> None:
        manifest = cross_repo_manifest()
        integration = next(node for node in manifest["nodes"] if node["id"] == "integration")
        self.assertEqual(integration["depends_on"], ["implementation-join"])
        contract.validate_workflow_manifest(manifest)

    def test_final_review_must_follow_all_integration_tasks(self) -> None:
        manifest = cross_repo_manifest()
        integration_b = task_node(
            "integration-b",
            "integration",
            "repo-b",
            BINDING_B,
            ["implementation-join"],
        )
        manifest["nodes"].insert(-1, integration_b)

        with self.assertRaisesRegex(ValueError, "all integration tasks"):
            contract.validate_workflow_manifest(manifest)

        final_review = next(node for node in manifest["nodes"] if node["id"] == "final-review")
        final_review["depends_on"] = ["integration", "integration-b"]
        contract.validate_workflow_manifest(manifest)

    def test_digest_pin_rejects_old_v1_shape_even_when_phase_names_match(self) -> None:
        manifest = cross_repo_manifest()
        current = methods.load_builtin_method("cross-repo-api-change")
        stale = copy.deepcopy(current)
        stale["version"] = 1
        stale["requirements"] = {}
        manifest["method"] = methods.method_reference(stale)

        with self.assertRaisesRegex(ValueError, "identity does not match|digest mismatch"):
            methods.validate_workflow_method(manifest, current)

    def test_adaptive_contract_only_can_start_before_future_cross_repo_topology_exists(self) -> None:
        spec = methods.load_builtin_method("cross-repo-api-change")
        manifest = {
            "schema_version": 1,
            "id": "cross-repo-adaptive-start",
            "created_at": "2026-09-19T16:21:00Z",
            "method": methods.method_reference(spec),
            "method_mode": "adaptive",
            "nodes": [
                task_node("contract", "contract", "repo-a", BINDING_A, []),
                {
                    "id": "contract-review",
                    "kind": "planner_checkpoint",
                    "phase": "contract_checkpoint",
                    "depends_on": ["contract"],
                },
            ],
        }
        contract.validate_workflow_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
