"""Synthetic-only parent transport mode preview: no live browser permit."""

from __future__ import annotations

import copy
import unittest
from unittest import mock

from local_agent.conversation import github_fabric_parent_fence_preview as preview
from tests.test_github_fabric_dispatch import admitted_children, operator_request


class ParentTransportFencePreviewTests(unittest.TestCase):
    def setUp(self):
        self.operator = operator_request()
        self.children = admitted_children()
        self.candidate = preview.build_preview(
            self.operator, self.children, transport_mode="github_first"
        )
        self.identifier = self.candidate["id"]
        self.head = "a" * 40

    def plan(self, *,
             transport_mode="github_first", index=None,
             records=None, enabled=True, writer_authorized=True, **updates):
        if records is None:
            records = {self.identifier: None}
        return preview.preflight_parent_transport_preview(
            self.operator, self.children, transport_mode=transport_mode,
            existing_index=index, existing_records=records,
            expected_head_sha=self.head,
            enabled=enabled, writer_authorized=writer_authorized,
            **updates,
        )

    def test_preview_has_no_execution_send_or_real_ack_authority(self):
        record = self.candidate
        self.assertEqual(record["phase"], "unattested_no_browser_authority")
        self.assertEqual(record["kind"], preview.KIND)
        self.assertIs(record["browser_send_authorized"], False)
        self.assertEqual(record["ack_state"], "not_attested")
        self.assertEqual(record["fence_epoch"], 1)
        self.assertEqual(record["project_id"], "local-agent")
        self.assertNotIn("bootstrap_text", repr(record))
        self.assertNotIn("child_conversation_url", repr(record))
        self.assertNotIn("read_token", repr(record))
        self.assertEqual(preview.parent_path(record["id"]), (
            "parents/" + record["id"] + ".json"
        ))


    def test_parent_identity_is_global_across_projects(self):
        parent = self.operator["parent_conversation_url"]
        original_id = preview.parent_id(parent)
        with mock.patch.object(preview, "_PROJECT", "growclip"):
            self.assertEqual(preview.parent_id(parent), original_id)
        with mock.patch.object(preview, "_PROJECT", "shelly-link"):
            self.assertEqual(preview.parent_id(parent), original_id)
        self.assertEqual(preview.parent_path(original_id), "parents/" + original_id + ".json")

    def test_invalid_unhashable_transport_label_fails_as_validation_error(self):
        record = copy.deepcopy(self.candidate)
        record["transport_mode"] = ["legacy_dom"]
        with self.assertRaisesRegex(ValueError, "record invalid"):
            preview.validate_record(record)

    def test_malformed_transport_input_denied_before_building_dispatch(self):
        # An unhashable caller value must be a deterministic validation error,
        # never an uncaught container TypeError at the trusted writer boundary.
        for invalid in (None, 0, ["github_first"], {"mode": "legacy_dom"}):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "Parent transport mode invalid"
            ):
                preview.build_preview(self.operator, self.children, transport_mode=invalid)

    def test_parent_index_capacity_is_a_hard_bound(self):
        identifiers = [f"parent-{i:032x}" for i in range(preview.MAX_PARENTS)]
        valid = {"schema_version": 1, "parent_ids": identifiers}
        self.assertEqual(preview.validate_index(valid), valid)
        with self.assertRaisesRegex(ValueError, "index invalid"):
            preview.validate_index({
                "schema_version": 1,
                "parent_ids": [*identifiers, f"parent-{preview.MAX_PARENTS:032x}"],
            })

    def test_opt_in_required_and_trusted_exact_fixture_only(self):
        with self.assertRaises(PermissionError):
            self.plan(enabled=False)
        with self.assertRaises(PermissionError):
            self.plan(writer_authorized=False)
        changed = copy.deepcopy(self.children)
        changed[0]["scope"]["summary"] = "PRIVATE CLIENT INPUT"
        with self.assertRaises(PermissionError):
            preview.build_preview(self.operator, changed, transport_mode="github_first")
        with self.assertRaises(ValueError):
            preview.build_preview(self.operator, self.children, transport_mode="other")

    def test_atomic_plan_and_exact_replay(self):
        plan = self.plan()
        self.assertEqual(plan.operation, "commit_atomic")
        self.assertEqual(plan.expected_head_sha, self.head)
        self.assertEqual(len(plan.writes), 2)
        self.assertEqual(
            [path for path, _ in plan.writes],
            [preview.parent_path(self.identifier), preview.INDEX_PATH],
        )
        self.assertEqual(plan.writes[0][1], self.candidate)
        index = plan.writes[1][1]
        self.assertEqual(index["parent_ids"], [self.identifier])
        self.assertEqual(
            self.plan(index=index, records={self.identifier: self.candidate}).operation,
            "replay",
        )
        self.assertEqual(
            self.plan(index=index, records={self.identifier: self.candidate}).writes,
            (),
        )

    def test_same_parent_legacy_vs_github_first_is_permanent_conflict(self):
        legacy = preview.build_preview(
            self.operator, self.children, transport_mode="legacy_dom"
        )
        self.assertEqual(legacy["id"], self.identifier)
        self.assertFalse(legacy["browser_send_authorized"])
        index = {"schema_version": 1, "parent_ids": [self.identifier]}
        with self.assertRaisesRegex(ValueError, "already occupied"):
            self.plan(index=index, records={self.identifier: legacy})
        # A second preview source cannot acquire this parent while a first
        # source is present, even when it uses the same workflow/child identities.
        with self.assertRaisesRegex(ValueError, "already occupied"):
            self.plan(
                transport_mode="legacy_dom",
                index=index, records={self.identifier: self.candidate}
            )

    def test_same_id_payload_change_and_fake_send_permission_rejected(self):
        index = {"schema_version": 1, "parent_ids": [self.identifier]}
        mutation = copy.deepcopy(self.candidate)
        mutation["operator_request_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "already occupied"):
            self.plan(index=index, records={self.identifier: mutation})
        mutation = copy.deepcopy(self.candidate)
        mutation["browser_send_authorized"] = True
        with self.assertRaisesRegex(ValueError, "record invalid"):
            self.plan(index=index, records={self.identifier: mutation})
        mutation = copy.deepcopy(self.candidate)
        mutation["ack_state"] = "browser_received"
        with self.assertRaisesRegex(ValueError, "record invalid"):
            self.plan(index=index, records={self.identifier: mutation})

    def test_no_implicit_lease_expiry_epoch_increase_or_mode_transfer(self):
        changed = copy.deepcopy(self.candidate)
        changed["fence_epoch"] = 2
        with self.assertRaisesRegex(ValueError, "record invalid"):
            preview.validate_record(changed)
        changed = copy.deepcopy(self.candidate)
        changed["phase"] = "leased"
        with self.assertRaisesRegex(ValueError, "record invalid"):
            preview.validate_record(changed)
        self.assertNotIn("expires_at", self.candidate)
        self.assertNotIn("allow_takeover", self.candidate)

    def test_incomplete_snapshot_or_dangling_or_orphan_record_refused(self):
        index = {"schema_version": 1, "parent_ids": [self.identifier]}
        with self.assertRaisesRegex(ValueError, "origin snapshot incomplete"):
            self.plan(index=index, records={})
        with self.assertRaisesRegex(ValueError, "dangling record"):
            self.plan(index=index, records={self.identifier: None})
        with self.assertRaisesRegex(ValueError, "not indexed"):
            self.plan(index=None, records={self.identifier: self.candidate})

    def test_corrupt_index_path_or_origin_sha_denied(self):
        with self.assertRaisesRegex(ValueError, "path identity invalid"):
            preview.parent_path("../escape")
        with self.assertRaises(ValueError):
            preview.validate_index({"schema_version": 1, "parent_ids": [
                self.identifier, self.identifier
            ]})
        with self.assertRaises(ValueError):
            preview.validate_index({"schema_version": True, "parent_ids": []})
        with self.assertRaises(ValueError):
            preview.validate_index({"schema_version": 1, "parent_ids": ["wrong"]})
        with self.assertRaisesRegex(ValueError, "exact origin SHA"):
            preview.preflight_parent_transport_preview(
                self.operator, self.children, transport_mode="github_first",
                existing_index=None, existing_records={self.identifier: None},
                expected_head_sha="not-a-sha", enabled=True, writer_authorized=True,
            )

    def test_noncanonical_or_unrelated_parent_never_rebinds(self):
        with self.assertRaises(ValueError):
            preview.parent_id("https://chatgpt.com/c/../invalid")
        mutation = copy.deepcopy(self.candidate)
        mutation["id"] = "parent-" + "0" * 32
        with self.assertRaisesRegex(ValueError, "record invalid"):
            preview.validate_record(mutation)
        mutation = copy.deepcopy(self.candidate)
        mutation["project_id"] = "growclip"
        with self.assertRaisesRegex(ValueError, "record invalid"):
            preview.validate_record(mutation)


if __name__ == "__main__":
    unittest.main()
