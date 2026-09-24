from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_agent.conversation import campaign, contract, records
from local_agent.conversation.record_store import WorkflowConversationRecordLedger
from local_agent.conversation.store import WorkflowConversationStore
from local_agent.workflow import contract as workflow_contract
from local_agent.workflow.store import WorkflowStore


BINDING = "12345678-1234-4abc-8def-1234567890ab"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
WORKFLOW_ID = "campaign-integration"
SOURCE_NODE = "source-reasoning"
TARGET_NODE = "target-reasoning"


def workflow_manifest() -> dict:
    return {
        "schema_version": workflow_contract.WORKFLOW_SCHEMA_VERSION,
        "id": WORKFLOW_ID,
        "created_at": "2026-09-24T00:00:00Z",
        "nodes": [
            {
                "id": SOURCE_NODE,
                "kind": "reasoning",
                "repository_id": "local-agent",
                "agent_binding": BINDING,
                "depends_on": [],
            },
            {
                "id": TARGET_NODE,
                "kind": "reasoning",
                "repository_id": "local-agent",
                "agent_binding": BINDING,
                "depends_on": [SOURCE_NODE],
            },
        ],
    }


def child_request(
    manifest: dict,
    *,
    request_id: str,
    node_id: str,
    created_at: str,
    context_refs: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": request_id,
        "workflow_id": manifest["id"],
        "workflow_node_id": node_id,
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": workflow_contract.manifest_digest(manifest),
        "parent_conversation_url": PARENT_URL,
        "created_at": created_at,
        "role": "verification",
        "repository_id": "local-agent",
        "agent_binding": BINDING,
        "repository_ref": "develop/conversation-fabric",
        "repository_commit_sha": "a" * 40,
        "scope": {
            "summary": f"Reason about {node_id} without importing transcript history.",
            "paths": ["local_agent/conversation"],
        },
        "context_refs": list(context_refs or []),
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }


def registration(request: dict) -> dict:
    token = "source" if request["workflow_node_id"] == SOURCE_NODE else "target"
    return {
        "schema_version": contract.CHILD_REGISTRATION_SCHEMA_VERSION,
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "parent_conversation_url": request["parent_conversation_url"],
        "child_conversation_url": f"https://chatgpt.com/c/{token}-conversation-001",
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


def checkpoint(request: dict, summary: str) -> dict:
    return {
        "schema_version": records.CHILD_CHECKPOINT_SCHEMA_VERSION,
        **provenance(request),
        "sequence": 1,
        "summary": summary,
        "evidence_refs": [],
        "recorded_at": "2026-09-24T00:04:00Z",
    }


def terminal(
    request: dict,
    *,
    summary: str = "Source reasoning completed.",
    recorded_at: str = "2026-09-24T00:05:00Z",
) -> dict:
    return {
        "schema_version": records.CHILD_TERMINAL_SCHEMA_VERSION,
        **provenance(request),
        "outcome": "succeeded",
        "summary": summary,
        "evidence_refs": [
            {
                "kind": "git_commit",
                "repository_id": "local-agent",
                "commit_sha": "b" * 40,
            }
        ],
        "recorded_at": recorded_at,
    }


class ConversationCampaignIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workflow_store = WorkflowStore(self.root)
        self.manifest = workflow_manifest()
        self.workflow_store.submit(self.manifest)
        self.conversations = WorkflowConversationStore(
            self.workflow_store,
            WORKFLOW_ID,
        )
        self.ledger = WorkflowConversationRecordLedger(self.conversations)
        self.source_request = child_request(
            self.manifest,
            request_id="child-source-001",
            node_id=SOURCE_NODE,
            created_at="2026-09-24T00:01:00Z",
        )
        self.conversations.admit_request(self.source_request)
        self.conversations.transition_state(
            self.source_request["id"],
            "registration_pending",
        )
        self.conversations.register_child(registration(self.source_request))

    def restarted(self) -> tuple[WorkflowConversationStore, WorkflowConversationRecordLedger]:
        workflow_store = WorkflowStore(self.root)
        conversations = WorkflowConversationStore(workflow_store, WORKFLOW_ID)
        return conversations, WorkflowConversationRecordLedger(conversations)

    def finish_source(self, *, summary: str = "Source reasoning completed.") -> dict:
        durable = terminal(self.source_request, summary=summary)
        self.ledger.record_terminal(durable)
        return durable

    def admit_target(
        self,
        context_refs: list[dict],
        *,
        created_at: str = "2026-09-24T00:06:00Z",
    ) -> dict:
        request = child_request(
            self.manifest,
            request_id="child-target-001",
            node_id=TARGET_NODE,
            created_at=created_at,
            context_refs=context_refs,
        )
        self.conversations.admit_request(request)
        return request

    def test_reconcile_repairs_terminal_recorded_before_workflow_state(self) -> None:
        candidate = terminal(self.source_request)
        with mock.patch.object(
            self.workflow_store,
            "set_node_state",
            side_effect=OSError("simulated workflow-state crash"),
        ):
            with self.assertRaisesRegex(OSError, "simulated workflow-state crash"):
                self.ledger.record_terminal(candidate)

        self.assertEqual(
            self.conversations.load_state(self.source_request["id"])["state"],
            "terminal_recorded",
        )
        conversations, ledger = self.restarted()
        result = campaign.reconcile_reasoning_children(conversations, ledger)

        self.assertEqual(result.recovered_child_states, ())
        self.assertEqual(result.reconciled_workflow_nodes, (SOURCE_NODE,))
        self.assertEqual(
            conversations.workflow_store.load_state(WORKFLOW_ID)["node_states"][SOURCE_NODE],
            "succeeded",
        )
        self.assertEqual(
            campaign.reconcile_reasoning_children(conversations, ledger),
            campaign.ReasoningReconcileResult(),
        )

    def test_reconcile_repairs_terminal_write_before_child_state(self) -> None:
        candidate = terminal(self.source_request)
        actual_write = self.conversations._write_state

        def fail_terminal_recorded(request_id: str, payload: dict) -> None:
            if payload["state"] == "terminal_recorded":
                raise OSError("simulated child-state crash")
            actual_write(request_id, payload)

        with mock.patch.object(
            self.conversations,
            "_write_state",
            side_effect=fail_terminal_recorded,
        ):
            with self.assertRaisesRegex(OSError, "simulated child-state crash"):
                self.ledger.record_terminal(candidate)

        conversations, ledger = self.restarted()
        result = campaign.reconcile_reasoning_children(conversations, ledger)
        self.assertEqual(result.recovered_child_states, (self.source_request["id"],))
        self.assertEqual(result.reconciled_workflow_nodes, (SOURCE_NODE,))
        self.assertEqual(
            conversations.load_state(self.source_request["id"])["state"],
            "terminal_recorded",
        )

    def test_reconcile_rejects_workflow_success_without_durable_terminal(self) -> None:
        self.workflow_store.set_node_state(WORKFLOW_ID, SOURCE_NODE, "succeeded")
        with self.assertRaisesRegex(ValueError, "without a durable child terminal"):
            campaign.reconcile_reasoning_children(self.conversations, self.ledger)

    def test_projection_is_compact_and_references_durable_records(self) -> None:
        checkpoint_summary = "c" * 1500
        terminal_summary = "t" * 2000
        self.ledger.append_checkpoint(checkpoint(self.source_request, checkpoint_summary))
        durable = self.finish_source(summary=terminal_summary)

        projection = campaign.project_parent_ledger(self.conversations, self.ledger)
        self.assertEqual(projection["workflow_id"], WORKFLOW_ID)
        self.assertEqual(projection["node_states"][SOURCE_NODE], "succeeded")
        child = projection["reasoning_children"][0]
        self.assertEqual(child["child_request_id"], self.source_request["id"])
        self.assertEqual(child["lifecycle_state"], "terminal_recorded")
        self.assertEqual(
            len(child["latest_checkpoint"]["summary"]),
            campaign.MAX_LEDGER_SUMMARY_CHARS,
        )
        self.assertTrue(child["latest_checkpoint"]["summary_truncated"])
        self.assertEqual(
            len(child["terminal"]["summary"]),
            campaign.MAX_LEDGER_SUMMARY_CHARS,
        )
        self.assertTrue(child["terminal"]["summary_truncated"])
        self.assertEqual(child["terminal"]["evidence_ref_count"], 1)
        self.assertNotIn("evidence_refs", child["terminal"])
        self.assertEqual(
            child["terminal"]["record_ref"],
            {
                "kind": campaign.CHILD_TERMINAL_CONTEXT_KIND,
                "id": self.source_request["id"],
                "digest": records.child_terminal_digest(
                    durable,
                    request=self.source_request,
                ),
            },
        )

    def test_context_selection_resolves_only_explicit_exact_terminal_refs(self) -> None:
        durable = self.finish_source()
        terminal_ref = {
            "kind": campaign.CHILD_TERMINAL_CONTEXT_KIND,
            "id": self.source_request["id"],
            "digest": records.child_terminal_digest(
                durable,
                request=self.source_request,
            ),
        }
        target = self.admit_target(
            [
                {
                    "kind": "finding",
                    "id": "finding-001",
                    "digest": "sha256:" + "9" * 64,
                },
                terminal_ref,
            ]
        )

        selected = campaign.select_child_terminal_context(
            self.conversations,
            target["id"],
            self.ledger,
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["id"], self.source_request["id"])
        self.assertEqual(selected[0]["summary"], durable["summary"])
        self.assertEqual(selected[0]["evidence_refs"], durable["evidence_refs"])

    def test_context_selection_does_not_promote_unreferenced_terminal(self) -> None:
        self.finish_source()
        target = self.admit_target(
            [
                {
                    "kind": "finding",
                    "id": "finding-001",
                    "digest": "sha256:" + "8" * 64,
                }
            ]
        )
        self.assertEqual(
            campaign.select_child_terminal_context(
                self.conversations,
                target["id"],
                self.ledger,
            ),
            [],
        )

    def test_context_selection_rejects_wrong_terminal_digest(self) -> None:
        self.finish_source()
        target = self.admit_target(
            [
                {
                    "kind": campaign.CHILD_TERMINAL_CONTEXT_KIND,
                    "id": self.source_request["id"],
                    "digest": "sha256:" + "0" * 64,
                }
            ]
        )
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            campaign.select_child_terminal_context(
                self.conversations,
                target["id"],
                self.ledger,
            )

    def test_context_selection_rejects_future_terminal(self) -> None:
        durable = self.finish_source()
        target = self.admit_target(
            [
                {
                    "kind": campaign.CHILD_TERMINAL_CONTEXT_KIND,
                    "id": self.source_request["id"],
                    "digest": records.child_terminal_digest(
                        durable,
                        request=self.source_request,
                    ),
                }
            ],
            created_at="2026-09-24T00:04:30Z",
        )
        with self.assertRaisesRegex(ValueError, "recorded after target request creation"):
            campaign.select_child_terminal_context(
                self.conversations,
                target["id"],
                self.ledger,
            )

    def test_projection_fails_closed_on_multiple_requests_for_one_node(self) -> None:
        duplicate = child_request(
            self.manifest,
            request_id="child-source-duplicate",
            node_id=SOURCE_NODE,
            created_at="2026-09-24T00:03:00Z",
        )
        self.conversations.admit_request(duplicate)
        with self.assertRaisesRegex(ValueError, "multiple durable child requests"):
            campaign.project_parent_ledger(self.conversations, self.ledger)


if __name__ == "__main__":
    unittest.main()
