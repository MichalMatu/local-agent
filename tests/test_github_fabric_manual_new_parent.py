"""No-Bridge, no-Send synthetic new-parent handoff preview regressions."""
from __future__ import annotations

import dataclasses
import unittest

from local_agent.conversation import github_fabric_manual_new_parent as preview

HEAD = "a" * 40
SOURCE = "https://chatgpt.com/c/old-parent"
DEST = "https://chatgpt.com/c/new-parent"


def private_observation():
    return {
        "source_kind": "private_synthetic_dispatch_unattested",
        "source_head_sha": HEAD,
        "project_id": "local-agent",
        "workflow_id": "wf-test",
        "operator_request_id": "request-1",
        "dispatch_id": "fabric-" + "b" * 32,
        "parent_conversation_url": SOURCE,
        "children": [{
            "request_id": "child-1", "spawn_transaction_id": "spawn-1",
            "child_request_digest": "sha256:" + "1" * 64,
            "bootstrap_digest": "sha256:" + "2" * 64,
            "execution_state": "published_execution_unconfirmed",
        }, {
            "request_id": "child-2", "spawn_transaction_id": "spawn-2",
            "child_request_digest": "sha256:" + "3" * 64,
            "bootstrap_digest": "sha256:" + "4" * 64,
            "execution_state": "published_execution_unconfirmed",
        }],
    }


def public_observation():
    return {
        "schema_version": 1,
        "source_kind": "public_synthetic_observation_only",
        "source_head_sha": HEAD,
        "workflow_id": "wf-test",
        "operator_request_id": "request-1",
        "dispatch_id": "fabric-" + "b" * 32,
        "parent_conversation_url": SOURCE,
        "children": [{
            "claim_id": "claim-1", "workflow_node_id": "node-1",
            "child_request_id": "child-1", "spawn_transaction_id": "spawn-1",
            "lifecycle": "published_execution_unconfirmed",
        }, {
            "claim_id": "claim-2", "workflow_node_id": "node-2",
            "child_request_id": "child-2", "spawn_transaction_id": "spawn-2",
            "lifecycle": "published_execution_unconfirmed",
        }],
    }


class ManualNewParentPreviewTests(unittest.TestCase):
    def inspect(self, observation=None, **kwargs):
        return preview.preview_manual_new_parent(
            observation if observation is not None else private_observation(),
            independently_pinned_source_sha=kwargs.get("head", HEAD),
            destination_parent_conversation_url=kwargs.get("destination", DEST),
        )

    def test_private_and_public_observation_are_read_only(self):
        for fixture in (private_observation, public_observation):
            with self.subTest(source=fixture):
                candidate = self.inspect(fixture())
                self.assertTrue(dataclasses.is_dataclass(candidate))
                self.assertTrue(candidate.__dataclass_params__.frozen)
                self.assertEqual(candidate.decision, "manual_read_only_review")
                self.assertFalse(candidate.browser_effects_permitted)
                self.assertFalse(candidate.automatic_retry_permitted)
                self.assertFalse(candidate.legacy_worker_retirement_proven)
                self.assertEqual(candidate.child_request_ids, ("child-1", "child-2"))
                self.assertNotIn("bootstrap_digest", dataclasses.asdict(candidate))

    def test_same_parent_and_alias_are_rejected(self):
        for dest in (SOURCE, "https://chat.openai.com/c/old-parent", SOURCE + "/"):
            with self.subTest(dest=dest), self.assertRaises(ValueError):
                self.inspect(destination=dest)

    def test_ref_and_source_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "source SHA"):
            self.inspect(head="b" * 40)
        o = private_observation()
        o["source_head_sha"] = "Z" * 40
        with self.assertRaisesRegex(ValueError, "source SHA"):
            self.inspect(o)

    def test_unapproved_urls_rejected(self):
        for dest in ("https://evil.com/c/new-parent", "http://chatgpt.com/c/new-parent",
                     "https://chatgpt.com/c/new-parent#hash", "https://chatgpt.com/"):
            with self.subTest(dest=dest), self.assertRaises(ValueError):
                self.inspect(destination=dest)
        o = private_observation()
        o["parent_conversation_url"] = "https://chat.openai.com/c/old-parent"
        with self.assertRaises(ValueError):
            self.inspect(o)

    def test_reject_private_prompt_or_new_unaudited_fields(self):
        for field in ("bootstrap_text", "token", "browser_send_authorized", "message"):
            o = private_observation()
            o[field] = "private content"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "envelope"):
                self.inspect(o)
        o = private_observation()
        o["children"][0]["prompt"] = "secret"
        with self.assertRaisesRegex(ValueError, "shape"):
            self.inspect(o)

    def test_reject_ack_or_execution_state_upgrade(self):
        for fixture in (private_observation, public_observation):
            o = fixture()
            field = "execution_state" if "project_id" in o else "lifecycle"
            o["children"][0][field] = "confirmed_terminal"
            with self.assertRaisesRegex(ValueError, "cannot prove"):
                self.inspect(o)

    def test_reject_truncated_duplicate_and_nonmapping_child(self):
        o = private_observation()
        o["children"].pop()
        with self.assertRaisesRegex(ValueError, "count"):
            self.inspect(o)
        o = private_observation()
        o["children"][1]["request_id"] = "child-1"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.inspect(o)
        o = private_observation()
        o["children"][0] = "bad"
        with self.assertRaisesRegex(ValueError, "shape"):
            self.inspect(o)

    def test_reject_invalid_child_digest(self):
        o = private_observation()
        o["children"][0]["bootstrap_digest"] = "not-digest"
        with self.assertRaisesRegex(ValueError, "digests"):
            self.inspect(o)

    def test_reject_unrecognized_source_kind_and_schema(self):
        o = private_observation()
        o["source_kind"] = "live_untrusted"
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.inspect(o)
        o = public_observation()
        o["schema_version"] = True
        with self.assertRaisesRegex(ValueError, "envelope"):
            self.inspect(o)

    def test_reject_bad_workflow_identity(self):
        o = private_observation()
        o["dispatch_id"] = "../file"
        with self.assertRaisesRegex(ValueError, "identities"):
            self.inspect(o)


if __name__ == "__main__":
    unittest.main()
