"""Portable synthetic handoff: integrity, pinning, and GET-only Git source recheck."""

from __future__ import annotations

import dataclasses
import json
import unittest

from local_agent.conversation import github_fabric_claims_github as claims_writer
from local_agent.conversation import github_fabric_github as public_git
from local_agent.conversation import github_fabric_manual_handoff as handoff
from local_agent.conversation import github_fabric_manual_new_parent as manual
from local_agent.conversation import github_fabric_private_github as private_git
from local_agent.conversation import github_fabric_private_recovery as private_reader
from local_agent.conversation import github_fabric_recovery as public_reader
from tests.test_github_fabric_claims import AtomicGitDataAPI
from tests.test_github_fabric_dispatch import admitted_children, operator_request
from tests.test_github_fabric_manual_new_parent import private_observation, public_observation, DEST
from tests.test_github_fabric_private_github import PrivateGitDataAPI

HEAD = "a" * 40


def fixture_manifest(private: bool = True) -> str:
    observed = private_observation() if private else public_observation()
    candidate = manual.preview_manual_new_parent(
        observed, independently_pinned_source_sha=HEAD,
        destination_parent_conversation_url=DEST,
    )
    return handoff.export_manual_handoff(candidate)


class PortableHandoffTests(unittest.TestCase):
    def parse(self, manifest=None, **options):
        return handoff.import_manual_handoff(
            manifest if manifest is not None else fixture_manifest(),
            independently_pinned_source_sha=options.get("pin", HEAD),
            expected_destination_parent_conversation_url=options.get("destination", DEST),
        )

    def test_private_and_public_deterministic_round_trip(self):
        for private in (True, False):
            with self.subTest(private=private):
                manifest = fixture_manifest(private)
                parsed = self.parse(manifest)
                self.assertTrue(dataclasses.is_dataclass(parsed))
                self.assertTrue(parsed.__dataclass_params__.frozen)
                self.assertEqual(handoff.export_manual_handoff(parsed), manifest)
                self.assertEqual(parsed.decision, "manual_read_only_review")
                self.assertFalse(parsed.browser_effects_permitted)
                self.assertFalse(parsed.automatic_retry_permitted)
                self.assertFalse(parsed.legacy_worker_retirement_proven)
                self.assertNotIn("bootstrap_text", manifest)
                self.assertNotIn("child_request_digest", manifest)
                self.assertNotIn("token", manifest)

    def test_wrong_sha_and_destination_rejected(self):
        with self.assertRaisesRegex(ValueError, "source SHA"):
            self.parse(pin="e" * 40)
        with self.assertRaisesRegex(ValueError, "destination parent mismatch"):
            self.parse(destination="https://chatgpt.com/c/another-new-parent")
        with self.assertRaises(ValueError):
            self.parse(destination="https://chat.openai.com/c/new-parent")

    def test_modified_digest_does_not_prove_integrity(self):
        value = json.loads(fixture_manifest())
        value["workflow_id"] = "tampered"
        altered = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.parse(altered)

    def test_malformed_canonical_or_duplicate_keys_rejected(self):
        text = fixture_manifest()
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            self.parse(text.replace('{"automatic_retry_permitted":false',
                                    '{"automatic_retry_permitted":false,"automatic_retry_permitted":false'))
        with self.assertRaisesRegex(ValueError, "canonical JSON"):
            self.parse(json.dumps(json.loads(text), indent=2))
        with self.assertRaisesRegex(ValueError, "input must be bounded"):
            self.parse(text + " " * handoff.MAX_MANIFEST_BYTES)
        with self.assertRaises(ValueError):
            self.parse('{"not":"complete"}')

    def test_new_authority_fields_and_true_permissions_rejected(self):
        value = json.loads(fixture_manifest())
        value["browser_effects_permitted"] = True
        value["manifest_digest"] = handoff._digest({
            key: item for key, item in value.items() if key != "manifest_digest"
        })
        with self.assertRaisesRegex(ValueError, "cannot grant execution"):
            self.parse(json.dumps(value, sort_keys=True, separators=(",", ":")))
        value = json.loads(fixture_manifest())
        value["prompt"] = "PRIVATE CREDENTIAL"
        with self.assertRaisesRegex(ValueError, "manifest fields"):
            self.parse(json.dumps(value, sort_keys=True, separators=(",", ":")))

    def test_bad_or_forged_preview_cannot_be_exported(self):
        with self.assertRaisesRegex(ValueError, "validated preview"):
            handoff.export_manual_handoff(private_observation())  # type: ignore[arg-type]
        obj = self.parse()
        forged = dataclasses.replace(obj, browser_effects_permitted=True)
        with self.assertRaisesRegex(ValueError, "cannot grant execution"):
            handoff.export_manual_handoff(forged)
        forged = dataclasses.replace(obj, child_request_ids=("child-1", "child-1"))
        with self.assertRaisesRegex(ValueError, "children identities"):
            handoff.export_manual_handoff(forged)

    def _published(self, private: bool):
        operator = operator_request()
        children = admitted_children()
        if private:
            api = PrivateGitDataAPI()
            private_git.publish_private_synthetic_fixture(
                operator, children, enabled=True, api=api
            )
            kind = private_reader.SOURCE_KIND
        else:
            api = AtomicGitDataAPI()
            public_git.publish_synthetic_fixture(
                operator, children, enabled=True, api=api
            )
            claims_writer.publish_synthetic_claims(
                operator, children, enabled=True, api=api
            )
            kind = public_reader.SOURCE_KIND
        source = manual.preview_manual_new_parent_from_github(
            operator, children, source_kind=kind,
            independently_pinned_source_sha=api.head,
            destination_parent_conversation_url=DEST,
            enabled=True, api=api,
        )
        return operator, children, api, handoff.export_manual_handoff(source)

    def test_verified_handoff_requires_fresh_get_only_public_private_recovery(self):
        for private in (True, False):
            with self.subTest(private=private):
                operator, children, api, manifest = self._published(private)
                original_head = api.head
                original_commits = len(api.commits)
                before = len(api.operations)
                result = handoff.verify_manual_handoff_against_github(
                    manifest, operator, children,
                    independently_pinned_source_sha=original_head,
                    expected_destination_parent_conversation_url=DEST,
                    api=api, enabled=True,
                )
                self.assertEqual(result, handoff.import_manual_handoff(
                    manifest, independently_pinned_source_sha=original_head,
                    expected_destination_parent_conversation_url=DEST,
                ))
                self.assertEqual(api.head, original_head)
                self.assertEqual(len(api.commits), original_commits)
                self.assertEqual({op[0] for op in api.operations[before:]}, {"GET"})

    def test_rehashed_workflow_tamper_fails_against_actual_github_source(self):
        operator, children, api, manifest = self._published(True)
        tampered = json.loads(manifest)
        tampered["workflow_id"] = "attacker-renamed-workflow"
        tampered["manifest_digest"] = handoff._digest({
            key: value for key, value in tampered.items() if key != "manifest_digest"
        })
        text = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
        # A transport digest is not authentication. The remote source recheck is.
        handoff.import_manual_handoff(
            text, independently_pinned_source_sha=api.head,
            expected_destination_parent_conversation_url=DEST,
        )
        with self.assertRaisesRegex(ValueError, "does not match GitHub"):
            handoff.verify_manual_handoff_against_github(
                text, operator, children,
                independently_pinned_source_sha=api.head,
                expected_destination_parent_conversation_url=DEST,
                api=api, enabled=True,
            )

    def test_disabled_and_invalid_manifest_emit_no_network_calls(self):
        operator, children, api, manifest = self._published(True)
        before = len(api.operations)
        kwargs = dict(
            independently_pinned_source_sha=api.head,
            expected_destination_parent_conversation_url=DEST,
            enabled=True, api=api,
        )
        with self.assertRaisesRegex(PermissionError, "default-disabled"):
            handoff.verify_manual_handoff_against_github(
                manifest, operator, children, **{**kwargs, "enabled": False}
            )
        with self.assertRaisesRegex(ValueError, "source SHA"):
            handoff.verify_manual_handoff_against_github(
                manifest, operator, children,
                **{**kwargs, "independently_pinned_source_sha": "e" * 40}
            )
        self.assertEqual(len(api.operations), before)

    def test_nonmatching_source_even_with_matching_pin_is_rejected(self):
        operator, children, api, manifest = self._published(True)
        # Known-public fixture preflight itself denies a modified source.
        operator["parent_conversation_url"] = "https://chatgpt.com/c/unrelated-parent"
        with self.assertRaises(PermissionError):
            handoff.verify_manual_handoff_against_github(
                manifest, operator, children,
                independently_pinned_source_sha=api.head,
                expected_destination_parent_conversation_url=DEST,
                api=api, enabled=True,
            )


if __name__ == "__main__":
    unittest.main()
