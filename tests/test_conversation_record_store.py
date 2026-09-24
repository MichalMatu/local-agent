from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_agent.conversation import contract, records
from local_agent.conversation.record_store import WorkflowConversationRecordLedger
from local_agent.conversation.store import WorkflowConversationStore
from local_agent.workflow import contract as workflow_contract
from local_agent.workflow.store import WorkflowStore


BINDING = "12345678-1234-4abc-8def-1234567890ab"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
CHILD_URL = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222"
WORKFLOW_ID = "record-ledger-workflow"
NODE_ID = "reasoning-node"


def workflow_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": WORKFLOW_ID,
        "created_at": "2026-09-24T00:00:00Z",
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


def child_request(manifest: dict) -> dict:
    return {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": "child-record-001",
        "workflow_id": manifest["id"],
        "workflow_node_id": NODE_ID,
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": workflow_contract.manifest_digest(manifest),
        "parent_conversation_url": PARENT_URL,
        "created_at": "2026-09-24T00:01:00Z",
        "role": "verification",
        "repository_id": "local-agent",
        "agent_binding": BINDING,
        "repository_ref": "main",
        "repository_commit_sha": "a" * 40,
        "scope": {"summary": "Verify the bounded change.", "paths": ["local_agent"]},
        "context_refs": [],
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }


def registration(request: dict) -> dict:
    return {
        "schema_version": contract.CHILD_REGISTRATION_SCHEMA_VERSION,
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "parent_conversation_url": request["parent_conversation_url"],
        "child_conversation_url": CHILD_URL,
        "registered_at": "2026-09-24T00:02:00Z",
    }


def provenance(request: dict) -> dict:
    return {
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "workflow_id": request["workflow_id"],
        "workflow_node_id": request["workflow_node_id"],
        "workflow_node_revision": request["workflow_node_revision"],
        "workflow_node_introduction_digest": request["workflow_node_introduction_digest"],
    }


def checkpoint(request: dict, sequence: int) -> dict:
    return {
        "schema_version": records.CHILD_CHECKPOINT_SCHEMA_VERSION,
        **provenance(request),
        "sequence": sequence,
        "summary": f"Checkpoint {sequence}.",
        "evidence_refs": [],
        "recorded_at": f"2026-09-24T00:{10 + sequence:02d}:00Z",
    }


def terminal(request: dict, outcome: str = "succeeded") -> dict:
    return {
        "schema_version": records.CHILD_TERMINAL_SCHEMA_VERSION,
        **provenance(request),
        "outcome": outcome,
        "summary": f"Reasoning child {outcome}.",
        "evidence_refs": [],
        "recorded_at": "2026-09-24T00:30:00Z",
    }


class ConversationRecordLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workflow_store = WorkflowStore(self.root)
        self.manifest = workflow_manifest()
        self.workflow_store.submit(self.manifest)
        self.conversations = WorkflowConversationStore(self.workflow_store, WORKFLOW_ID)
        self.request = child_request(self.manifest)
        self.conversations.admit_request(self.request)
        self.conversations.transition_state(self.request["id"], "registration_pending")
        self.conversations.register_child(registration(self.request))
        self.ledger = WorkflowConversationRecordLedger(self.conversations)

    def restarted_ledger(self) -> WorkflowConversationRecordLedger:
        workflow_store = WorkflowStore(self.root)
        conversations = WorkflowConversationStore(workflow_store, WORKFLOW_ID)
        return WorkflowConversationRecordLedger(conversations)

    def test_ledger_has_no_independent_root_or_lock(self) -> None:
        self.assertEqual(self.ledger.checkpoints_root.parent, self.conversations.root)
        self.assertEqual(self.ledger.terminals_root.parent, self.conversations.root)
        self.assertIs(self.ledger.store.workflow_store, self.workflow_store)

    def test_checkpoints_are_contiguous_append_only_and_restart_safe(self) -> None:
        first = checkpoint(self.request, 1)
        second = checkpoint(self.request, 2)
        self.assertEqual(self.ledger.append_checkpoint(first), first)
        self.assertEqual(self.ledger.append_checkpoint(second), second)

        restarted = self.restarted_ledger()
        self.assertEqual(restarted.load_checkpoints(self.request["id"]), [first, second])

        third = checkpoint(self.request, 3)
        restarted.append_checkpoint(third)
        self.assertEqual(
            [item["sequence"] for item in restarted.load_checkpoints(self.request["id"])],
            [1, 2, 3],
        )

    def test_checkpoint_retry_ignores_recorded_at_but_conflict_fails(self) -> None:
        first = checkpoint(self.request, 1)
        self.ledger.append_checkpoint(first)
        retry = copy.deepcopy(first)
        retry["recorded_at"] = "2026-09-24T00:19:00Z"
        self.assertEqual(self.ledger.append_checkpoint(retry), first)

        conflict = copy.deepcopy(first)
        conflict["summary"] = "Different semantic checkpoint."
        with self.assertRaisesRegex(ValueError, "different digest"):
            self.ledger.append_checkpoint(conflict)

    def test_checkpoint_gap_and_post_terminal_append_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "contiguous; expected 1"):
            self.ledger.append_checkpoint(checkpoint(self.request, 2))

        self.ledger.record_terminal(terminal(self.request))
        with self.assertRaisesRegex(ValueError, "require active child state"):
            self.ledger.append_checkpoint(checkpoint(self.request, 1))

    def test_success_terminal_completes_child_and_workflow(self) -> None:
        durable = self.ledger.record_terminal(terminal(self.request, "succeeded"))
        self.assertEqual(durable["outcome"], "succeeded")
        child_state = self.conversations.load_state(self.request["id"])
        self.assertEqual(child_state["state"], "terminal_recorded")
        workflow_state = self.workflow_store.load_state(WORKFLOW_ID)
        self.assertEqual(workflow_state["node_states"][NODE_ID], "succeeded")
        self.assertEqual(workflow_state["workflow_state"], "completed")

    def test_failed_terminal_fails_reasoning_node(self) -> None:
        self.ledger.record_terminal(terminal(self.request, "failed"))
        workflow_state = self.workflow_store.load_state(WORKFLOW_ID)
        self.assertEqual(workflow_state["node_states"][NODE_ID], "failed")
        self.assertEqual(workflow_state["workflow_state"], "failed")

    def test_terminal_is_create_once_and_timestamp_is_nonsemantic(self) -> None:
        first = terminal(self.request)
        self.assertEqual(self.ledger.record_terminal(first), first)
        retry = copy.deepcopy(first)
        retry["recorded_at"] = "2026-09-24T00:31:00Z"
        self.assertEqual(self.ledger.record_terminal(retry), first)

        conflict = copy.deepcopy(first)
        conflict["summary"] = "Conflicting terminal."
        with self.assertRaisesRegex(ValueError, "different digest"):
            self.ledger.record_terminal(conflict)

    def test_restart_recovers_after_pending_state_before_terminal_write(self) -> None:
        candidate = terminal(self.request)
        with mock.patch(
            "local_agent.conversation.record_store._create_only",
            side_effect=OSError("simulated create failure"),
        ):
            with self.assertRaisesRegex(OSError, "simulated create failure"):
                self.ledger.record_terminal(candidate)

        self.assertEqual(
            self.conversations.load_state(self.request["id"])["state"],
            "terminal_pending_evidence",
        )
        restarted = self.restarted_ledger()
        self.assertEqual(restarted.record_terminal(candidate), candidate)
        self.assertEqual(
            restarted.store.load_state(self.request["id"])["state"],
            "terminal_recorded",
        )

    def test_restart_recovers_after_terminal_write_before_child_state(self) -> None:
        candidate = terminal(self.request)
        actual_write = self.conversations._write_state

        def fail_terminal_recorded(request_id: str, payload: dict) -> None:
            if payload["state"] == "terminal_recorded":
                raise OSError("simulated child-state failure")
            actual_write(request_id, payload)

        with mock.patch.object(
            self.conversations,
            "_write_state",
            side_effect=fail_terminal_recorded,
        ):
            with self.assertRaisesRegex(OSError, "simulated child-state failure"):
                self.ledger.record_terminal(candidate)

        self.assertEqual(self.ledger.load_terminal(self.request["id"]), candidate)
        self.assertEqual(
            self.conversations.load_state(self.request["id"])["state"],
            "terminal_pending_evidence",
        )
        restarted = self.restarted_ledger()
        self.assertEqual(restarted.record_terminal(candidate), candidate)
        self.assertEqual(
            restarted.store.load_state(self.request["id"])["state"],
            "terminal_recorded",
        )

    def test_retry_reconciles_workflow_after_child_terminal_is_recorded(self) -> None:
        candidate = terminal(self.request)
        with mock.patch.object(
            self.workflow_store,
            "set_node_state",
            side_effect=OSError("simulated workflow-state failure"),
        ):
            with self.assertRaisesRegex(OSError, "simulated workflow-state failure"):
                self.ledger.record_terminal(candidate)

        self.assertEqual(
            self.conversations.load_state(self.request["id"])["state"],
            "terminal_recorded",
        )
        self.assertEqual(
            self.workflow_store.load_state(WORKFLOW_ID)["node_states"][NODE_ID],
            "waiting_conversation",
        )

        restarted = self.restarted_ledger()
        self.assertEqual(restarted.record_terminal(candidate), candidate)
        self.assertEqual(
            restarted.store.workflow_store.load_state(WORKFLOW_ID)["node_states"][NODE_ID],
            "succeeded",
        )


if __name__ == "__main__":
    unittest.main()
