from __future__ import annotations

import copy
import unittest

from local_agent.conversation import contract, github_fabric_dispatch, operator_contract


PARENT = "https://chatgpt.com/c/6ac6840c-eaec-83ed-bde2-6971e9ffa220"
BINDING = "2180d453-1357-4fbc-be1a-e1e5b8fbb10a"


def operator_request() -> dict:
    return {
        "schema_version": operator_contract.OPERATOR_REQUEST_SCHEMA_VERSION,
        "id": "operator-request-001",
        "workflow_id": "workflow-001",
        "parent_conversation_url": PARENT,
        "repository_ids": ["local-agent"],
        "children": [
            {
                "request_id": "child-research",
                "node_id": "research",
                "role": "research",
                "summary": "Audit the bounded transport.",
                "paths": ["chat_bridge"],
            },
            {
                "request_id": "child-verify",
                "node_id": "verify",
                "role": "verification",
                "summary": "Verify the bounded transport.",
                "paths": ["local_agent/conversation"],
            },
        ],
    }


def child_request(request_id: str, node_id: str, role: str, summary: str, paths: list[str]) -> dict:
    request = {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": request_id,
        "workflow_id": "workflow-001",
        "workflow_node_id": node_id,
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": "sha256:" + "1" * 64,
        "parent_conversation_url": PARENT,
        "created_at": "2026-10-07T20:00:00Z",
        "role": role,
        "repository_id": "local-agent",
        "agent_binding": BINDING,
        "repository_ref": "main",
        "repository_commit_sha": "a" * 40,
        "scope": {"summary": summary, "paths": paths},
        "context_refs": [],
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }
    contract.validate_child_request(request)
    return request


def admitted_children() -> list[dict]:
    return [
        child_request(
            "child-research",
            "research",
            "research",
            "Audit the bounded transport.",
            ["chat_bridge"],
        ),
        child_request(
            "child-verify",
            "verify",
            "verification",
            "Verify the bounded transport.",
            ["local_agent/conversation"],
        ),
    ]


class GithubFabricDispatchTests(unittest.TestCase):
    def test_build_is_deterministic_and_projects_exact_existing_spawn_evidence(self) -> None:
        request = operator_request()
        children = admitted_children()

        first = github_fabric_dispatch.build_github_fabric_dispatch(request, children)
        second = github_fabric_dispatch.build_github_fabric_dispatch(
            copy.deepcopy(request),
            list(reversed(copy.deepcopy(children))),
        )

        self.assertEqual(first, second)
        github_fabric_dispatch.validate_github_fabric_dispatch(first)
        self.assertEqual(first["request_id"], request["id"])
        self.assertEqual(
            first["request_digest"],
            operator_contract.operator_request_digest(request),
        )
        self.assertRegex(first["campaign_id"], r"^cf-[0-9a-f]{16}$")
        self.assertEqual(
            [child["request_id"] for child in first["children"]],
            ["child-research", "child-verify"],
        )
        self.assertTrue(
            all(child["spawn"]["transaction_id"].startswith("spawn-") for child in first["children"])
        )
        self.assertTrue(
            all(
                child["spawn"]["child_request_digest"].startswith("sha256:")
                for child in first["children"]
            )
        )
        self.assertTrue(
            all(
                child["spawn"]["bootstrap_digest"].startswith("sha256:")
                for child in first["children"]
            )
        )
        self.assertTrue(
            all(
                child["spawn"]["bootstrap_text"].startswith("LOCAL AGENT CHILD BOOTSTRAP\n")
                for child in first["children"]
            )
        )

    def test_dispatch_has_no_browser_runtime_identity_or_top_level_execution_authority(self) -> None:
        dispatch = github_fabric_dispatch.build_github_fabric_dispatch(
            operator_request(),
            admitted_children(),
        )

        self.assertNotIn("tab_id", dispatch)
        for child in dispatch["children"]:
            self.assertNotIn("tab_id", child["spawn"])
            self.assertNotIn("agent_binding", child)
            self.assertNotIn("repository_id", child)
            self.assertNotIn("scheduler_resources", child)

    def test_same_id_changed_payload_is_a_permanent_conflict(self) -> None:
        dispatch = github_fabric_dispatch.build_github_fabric_dispatch(
            operator_request(),
            admitted_children(),
        )
        self.assertEqual(
            github_fabric_dispatch.reconcile_github_fabric_dispatch(dispatch, copy.deepcopy(dispatch)),
            dispatch,
        )

        changed = copy.deepcopy(dispatch)
        changed["children"][0]["spawn"]["bootstrap_text"] += "\nchanged"
        with self.assertRaisesRegex(ValueError, "same-id dispatch conflict"):
            github_fabric_dispatch.reconcile_github_fabric_dispatch(dispatch, changed)

    def test_admitted_children_must_match_operator_request_exactly(self) -> None:
        request = operator_request()
        children = admitted_children()
        children[0]["role"] = "integration"

        with self.assertRaisesRegex(ValueError, "role does not match"):
            github_fabric_dispatch.build_github_fabric_dispatch(request, children)

    def test_missing_or_extra_child_is_rejected(self) -> None:
        request = operator_request()
        children = admitted_children()

        with self.assertRaisesRegex(ValueError, "do not match operator request"):
            github_fabric_dispatch.build_github_fabric_dispatch(request, children[:1])

        extra = child_request(
            "child-extra",
            "extra",
            "integration",
            "Extra child.",
            ["docs"],
        )
        with self.assertRaisesRegex(ValueError, "do not match operator request"):
            github_fabric_dispatch.build_github_fabric_dispatch(request, children + [extra])


if __name__ == "__main__":
    unittest.main()
