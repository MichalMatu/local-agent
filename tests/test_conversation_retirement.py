from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from local_agent.conversation import contract, records
from local_agent.conversation.record_store import WorkflowConversationRecordLedger
from local_agent.conversation.retirement import (
    WorkflowConversationRetirement,
    build_retirement_receipt,
)
from local_agent.conversation.store import WorkflowConversationStore
from local_agent.workflow import contract as workflow_contract
from local_agent.workflow.store import WorkflowStore


BINDING = "12345678-1234-4abc-8def-1234567890ab"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
CHILD_URL = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222"
WORKFLOW_ID = "retirement-workflow"
NODE_ID = "reasoning-child"


def workflow() -> dict:
    return {
        "schema_version": workflow_contract.WORKFLOW_SCHEMA_VERSION,
        "id": WORKFLOW_ID,
        "created_at": "2026-09-24T12:00:00Z",
        "nodes": [
            {
                "id": NODE_ID,
                "kind": "reasoning",
                "repository_id": "local-agent",
                "agent_binding": BINDING,
                "depends_on": [],
            }
        ],
    }


def request(manifest: dict) -> dict:
    return {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": "child-retire-001",
        "workflow_id": manifest["id"],
        "workflow_node_id": NODE_ID,
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": workflow_contract.manifest_digest(manifest),
        "parent_conversation_url": PARENT_URL,
        "created_at": "2026-09-24T12:01:00Z",
        "role": "verification",
        "repository_id": "local-agent",
        "agent_binding": BINDING,
        "repository_ref": "develop/conversation-fabric",
        "repository_commit_sha": "a" * 40,
        "scope": {"summary": "Verify safe child retirement.", "paths": ["local_agent/conversation"]},
        "context_refs": [],
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }


def registration(source: dict) -> dict:
    return {
        "schema_version": contract.CHILD_REGISTRATION_SCHEMA_VERSION,
        "child_request_id": source["id"],
        "child_request_digest": contract.child_request_digest(source),
        "parent_conversation_url": source["parent_conversation_url"],
        "child_conversation_url": CHILD_URL,
        "registered_at": "2026-09-24T12:02:00Z",
    }


def terminal(source: dict) -> dict:
    return {
        "schema_version": records.CHILD_TERMINAL_SCHEMA_VERSION,
        "child_request_id": source["id"],
        "child_request_digest": contract.child_request_digest(source),
        "workflow_id": source["workflow_id"],
        "workflow_node_id": source["workflow_node_id"],
        "workflow_node_revision": source["workflow_node_revision"],
        "workflow_node_introduction_digest": source["workflow_node_introduction_digest"],
        "outcome": "succeeded",
        "summary": "Child completed and durable terminal evidence is recorded.",
        "evidence_refs": [],
        "recorded_at": "2026-09-24T12:10:00Z",
    }


class ConversationRetirementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        workflow_store = WorkflowStore(Path(self.tmp.name))
        self.workflow = workflow()
        workflow_store.submit(self.workflow)
        self.store = WorkflowConversationStore(workflow_store, WORKFLOW_ID)
        self.ledger = WorkflowConversationRecordLedger(self.store)
        self.retirement = WorkflowConversationRetirement(self.store, self.ledger)
        self.request = request(self.workflow)
        self.store.admit_request(self.request)
        self.store.transition_state(self.request["id"], "registration_pending")
        self.store.register_child(registration(self.request))

    def test_close_authority_requires_durable_terminal_record(self) -> None:
        with self.assertRaisesRegex(ValueError, "durable terminal record"):
            self.retirement.issue_close_authority(self.request["id"])
        self.assertEqual(self.store.load_state(self.request["id"])["state"], "active")

    def test_terminal_record_issues_exact_close_authority(self) -> None:
        durable = self.ledger.record_terminal(terminal(self.request))
        authority = self.retirement.issue_close_authority(self.request["id"])
        self.assertEqual(authority["child_request_id"], self.request["id"])
        self.assertEqual(authority["child_conversation_url"], CHILD_URL)
        self.assertEqual(
            authority["terminal_digest"],
            records.child_terminal_digest(durable, request=self.request),
        )
        self.assertEqual(self.store.load_state(self.request["id"])["state"], "terminal_recorded")

    def test_close_receipt_is_required_before_retired_state(self) -> None:
        self.ledger.record_terminal(terminal(self.request))
        authority = self.retirement.issue_close_authority(self.request["id"])
        self.assertEqual(self.store.load_state(self.request["id"])["state"], "terminal_recorded")

        receipt = build_retirement_receipt(authority, result="closed")
        retired = self.retirement.confirm_closed(self.request["id"], receipt)
        self.assertEqual(retired["state"], "retired")
        self.assertEqual(
            self.retirement.confirm_closed(self.request["id"], receipt)["state"],
            "retired",
        )

    def test_already_closed_is_valid_recovery_receipt(self) -> None:
        self.ledger.record_terminal(terminal(self.request))
        authority = self.retirement.issue_close_authority(self.request["id"])
        receipt = build_retirement_receipt(authority, result="already_closed")
        self.assertEqual(
            self.retirement.confirm_closed(self.request["id"], receipt)["state"],
            "retired",
        )

    def test_tampered_close_receipt_fails_closed(self) -> None:
        self.ledger.record_terminal(terminal(self.request))
        authority = self.retirement.issue_close_authority(self.request["id"])
        receipt = build_retirement_receipt(authority, result="closed")

        for field, value in (
            ("child_request_digest", "sha256:" + "0" * 64),
            ("child_conversation_url", "https://chatgpt.com/c/33333333-3333-4333-8333-333333333333"),
            ("terminal_digest", "sha256:" + "9" * 64),
        ):
            candidate = copy.deepcopy(receipt)
            candidate[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "does not match durable authority"):
                    self.retirement.confirm_closed(self.request["id"], candidate)
        self.assertEqual(self.store.load_state(self.request["id"])["state"], "terminal_recorded")

    def test_retired_child_cannot_issue_new_close_authority(self) -> None:
        self.ledger.record_terminal(terminal(self.request))
        authority = self.retirement.issue_close_authority(self.request["id"])
        self.retirement.confirm_closed(
            self.request["id"],
            build_retirement_receipt(authority, result="closed"),
        )
        with self.assertRaisesRegex(ValueError, "requires terminal_recorded state"):
            self.retirement.issue_close_authority(self.request["id"])


if __name__ == "__main__":
    unittest.main()
