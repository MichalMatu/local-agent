from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.conversation import campaign
from local_agent.conversation.record_store import WorkflowConversationRecordLedger
from local_agent.conversation.store import WorkflowConversationStore
from local_agent.workflow.store import WorkflowStore
from tests import test_conversation_campaign as fixtures


class ConversationCampaignBoundsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workflow_store = WorkflowStore(self.root)
        self.manifest = fixtures.workflow_manifest()
        self.workflow_store.submit(self.manifest)
        self.conversations = WorkflowConversationStore(
            self.workflow_store,
            fixtures.WORKFLOW_ID,
        )
        self.ledger = WorkflowConversationRecordLedger(self.conversations)
        self.source = fixtures.child_request(
            self.manifest,
            request_id="child-source-001",
            node_id=fixtures.SOURCE_NODE,
            created_at="2026-09-24T00:01:00Z",
        )
        self.conversations.admit_request(self.source)
        self.conversations.transition_state(self.source["id"], "registration_pending")
        self.conversations.register_child(fixtures.registration(self.source))
        self.ledger.record_terminal(fixtures.terminal(self.source))

    def _admit_target(self, context_refs: list[dict]) -> dict:
        target = fixtures.child_request(
            self.manifest,
            request_id="child-target-001",
            node_id=fixtures.TARGET_NODE,
            created_at="2026-09-24T00:06:00Z",
            context_refs=context_refs,
        )
        self.conversations.admit_request(target)
        return target

    def test_selected_child_terminal_context_count_is_bounded(self) -> None:
        refs = [
            {
                "kind": campaign.CHILD_TERMINAL_CONTEXT_KIND,
                "id": f"unavailable-child-{index:02d}",
                "digest": "sha256:" + f"{index:064x}",
            }
            for index in range(campaign.MAX_SELECTED_CONTEXT_RECORDS + 1)
        ]
        target = self._admit_target(refs)

        with self.assertRaisesRegex(ValueError, "exceeds 16 records"):
            campaign.select_child_terminal_context(
                self.conversations,
                target["id"],
                self.ledger,
            )

    def test_child_terminal_context_cannot_reference_target_itself(self) -> None:
        target_id = "child-target-001"
        target = self._admit_target(
            [
                {
                    "kind": campaign.CHILD_TERMINAL_CONTEXT_KIND,
                    "id": target_id,
                    "digest": "sha256:" + "f" * 64,
                }
            ]
        )

        with self.assertRaisesRegex(ValueError, "cannot select its own terminal"):
            campaign.select_child_terminal_context(
                self.conversations,
                target["id"],
                self.ledger,
            )


if __name__ == "__main__":
    unittest.main()
