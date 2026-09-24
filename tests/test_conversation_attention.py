from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_agent.conversation import attention, contract, records
from local_agent.conversation.record_store import WorkflowConversationRecordLedger
from local_agent.conversation.store import WorkflowConversationStore
from local_agent.foundation import result_events
from local_agent.workflow import contract as workflow_contract
from local_agent.workflow.store import WorkflowStore


BINDING = "12345678-1234-4abc-8def-1234567890ab"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
WORKFLOW_ID = "attention-workflow"
NODE_ID = "reasoning-node"


def manifest() -> dict:
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


def request(workflow: dict) -> dict:
    return {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": "child-attention-001",
        "workflow_id": WORKFLOW_ID,
        "workflow_node_id": NODE_ID,
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": workflow_contract.manifest_digest(workflow),
        "parent_conversation_url": PARENT_URL,
        "created_at": "2026-09-24T00:01:00Z",
        "role": "verification",
        "repository_id": "local-agent",
        "agent_binding": BINDING,
        "repository_ref": "develop/conversation-fabric",
        "repository_commit_sha": "a" * 40,
        "scope": {"summary": "Verify parent attention routing.", "paths": ["local_agent"]},
        "context_refs": [],
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }


def registration(child_request: dict) -> dict:
    return {
        "schema_version": contract.CHILD_REGISTRATION_SCHEMA_VERSION,
        "child_request_id": child_request["id"],
        "child_request_digest": contract.child_request_digest(child_request),
        "parent_conversation_url": child_request["parent_conversation_url"],
        "child_conversation_url": "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222",
        "registered_at": "2026-09-24T00:02:00Z",
    }


def terminal(child_request: dict, outcome: str = "succeeded") -> dict:
    return {
        "schema_version": records.CHILD_TERMINAL_SCHEMA_VERSION,
        "child_request_id": child_request["id"],
        "child_request_digest": contract.child_request_digest(child_request),
        "workflow_id": child_request["workflow_id"],
        "workflow_node_id": child_request["workflow_node_id"],
        "workflow_node_revision": child_request["workflow_node_revision"],
        "workflow_node_introduction_digest": child_request[
            "workflow_node_introduction_digest"
        ],
        "outcome": outcome,
        "summary": "Reasoning child completed its bounded scope.",
        "evidence_refs": [],
        "recorded_at": "2026-09-24T00:30:00Z",
    }


class ConversationAttentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def stack(self) -> tuple[WorkflowStore, WorkflowConversationStore, dict, dict]:
        workflow_store = WorkflowStore(self.root / "workflows")
        workflow = manifest()
        workflow_store.submit(workflow)
        conversations = WorkflowConversationStore(workflow_store, WORKFLOW_ID)
        child_request = request(workflow)
        conversations.admit_request(child_request)
        conversations.transition_state(child_request["id"], "registration_pending")
        conversations.register_child(registration(child_request))
        return workflow_store, conversations, child_request, terminal(child_request)

    def test_child_terminal_event_is_deterministic_bounded_and_parent_addressed(self) -> None:
        _, _, child_request, child_terminal = self.stack()
        first = attention.build_child_terminal_attention_event(
            child_request,
            child_terminal,
            emitted_at="2026-09-24T01:00:00+00:00",
        )
        second = attention.build_child_terminal_attention_event(
            child_request,
            child_terminal,
            emitted_at="2026-09-24T01:01:00+00:00",
        )
        self.assertEqual(first["event_type"], result_events.EVENT_TYPE_CHILD_TERMINAL_READY)
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["parent_conversation_url"], PARENT_URL)
        self.assertEqual(first["workflow_id"], WORKFLOW_ID)
        self.assertEqual(first["workflow_node_id"], NODE_ID)
        self.assertEqual(first["child_request_id"], child_request["id"])
        self.assertEqual(first["outcome"], "succeeded")
        state_dir = self.root / "event-state"
        result_events.enqueue_event(first, state_dir=state_dir)
        result_events.enqueue_event(second, state_dir=state_dir)
        pending = result_events.pending_events(state_dir=state_dir)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["emitted_at"], first["emitted_at"])

    def test_child_terminal_event_rejects_noncanonical_parent_and_digest(self) -> None:
        _, _, child_request, child_terminal = self.stack()
        with self.assertRaisesRegex(ValueError, "ChatGPT origin"):
            result_events.build_child_terminal_event(
                parent_conversation_url="https://example.com/c/nope",
                workflow_id=WORKFLOW_ID,
                workflow_node_id=NODE_ID,
                child_request_id=child_request["id"],
                child_request_digest=contract.child_request_digest(child_request),
                terminal_digest=records.child_terminal_digest(
                    child_terminal, request=child_request
                ),
                outcome="succeeded",
            )
        with self.assertRaisesRegex(ValueError, "terminal_digest"):
            result_events.build_child_terminal_event(
                parent_conversation_url=PARENT_URL,
                workflow_id=WORKFLOW_ID,
                workflow_node_id=NODE_ID,
                child_request_id=child_request["id"],
                child_request_digest=contract.child_request_digest(child_request),
                terminal_digest="not-a-digest",
                outcome="succeeded",
            )

    def test_default_ledger_remains_inert(self) -> None:
        _, conversations, child_request, child_terminal = self.stack()
        ledger = WorkflowConversationRecordLedger(conversations)
        with mock.patch.object(attention, "enqueue_child_terminal_attention") as enqueue:
            self.assertEqual(ledger.record_terminal(child_terminal), child_terminal)
        enqueue.assert_not_called()
        self.assertEqual(conversations.load_state(child_request["id"])["state"], "terminal_recorded")

    def test_opt_in_ledger_enqueues_after_workflow_outcome(self) -> None:
        workflow_store, conversations, child_request, child_terminal = self.stack()
        event_state = self.root / "bridge-state"
        ledger = WorkflowConversationRecordLedger(
            conversations,
            bridge_event_state_dir=event_state,
        )
        ledger.record_terminal(child_terminal)
        workflow = workflow_store.load_state(WORKFLOW_ID)
        self.assertEqual(workflow["node_states"][NODE_ID], "succeeded")
        pending = result_events.pending_events(state_dir=event_state)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["event_type"], "child_terminal_ready")
        self.assertEqual(pending[0]["parent_conversation_url"], PARENT_URL)
        self.assertEqual(pending[0]["workflow_id"], WORKFLOW_ID)
        self.assertEqual(pending[0]["child_request_id"], child_request["id"])

    def test_attention_enqueue_failure_is_restart_safe_and_idempotent(self) -> None:
        workflow_store, conversations, child_request, child_terminal = self.stack()
        event_state = self.root / "bridge-state"
        ledger = WorkflowConversationRecordLedger(
            conversations,
            bridge_event_state_dir=event_state,
        )
        with mock.patch.object(
            attention,
            "enqueue_child_terminal_attention",
            side_effect=OSError("simulated attention outbox failure"),
        ):
            with self.assertRaisesRegex(OSError, "attention outbox failure"):
                ledger.record_terminal(child_terminal)

        self.assertEqual(conversations.load_state(child_request["id"])["state"], "terminal_recorded")
        self.assertEqual(
            workflow_store.load_state(WORKFLOW_ID)["node_states"][NODE_ID],
            "succeeded",
        )
        self.assertEqual(result_events.pending_events(state_dir=event_state), [])

        restarted = WorkflowConversationRecordLedger(
            WorkflowConversationStore(WorkflowStore(self.root / "workflows"), WORKFLOW_ID),
            bridge_event_state_dir=event_state,
        )
        self.assertEqual(restarted.record_terminal(child_terminal), child_terminal)
        self.assertEqual(len(result_events.pending_events(state_dir=event_state)), 1)
        self.assertEqual(restarted.record_terminal(child_terminal), child_terminal)
        self.assertEqual(len(result_events.pending_events(state_dir=event_state)), 1)

    def test_workflow_reconcile_failure_does_not_emit_attention(self) -> None:
        workflow_store, conversations, _, child_terminal = self.stack()
        ledger = WorkflowConversationRecordLedger(
            conversations,
            bridge_event_state_dir=self.root / "bridge-state",
        )
        with (
            mock.patch.object(
                workflow_store,
                "set_node_state",
                side_effect=OSError("simulated workflow failure"),
            ),
            mock.patch.object(attention, "enqueue_child_terminal_attention") as enqueue,
        ):
            with self.assertRaisesRegex(OSError, "workflow failure"):
                ledger.record_terminal(child_terminal)
        enqueue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
