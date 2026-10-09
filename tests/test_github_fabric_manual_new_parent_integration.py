"""Integration of manual new-parent review with existing synthetic Git readers.

These tests use the repository's isolated in-memory Git APIs. No real GitHub
writes, browser effects, Chat Bridge, or agent tasks are performed.
"""

from __future__ import annotations

import unittest

from local_agent.conversation import github_fabric_claims_github as claims_writer
from local_agent.conversation import github_fabric_github as public_git
from local_agent.conversation import github_fabric_manual_new_parent as manual
from local_agent.conversation import github_fabric_private_github as private_git
from local_agent.conversation import github_fabric_private_recovery as private_reader
from local_agent.conversation import github_fabric_recovery as public_reader
from tests.test_github_fabric_claims import AtomicGitDataAPI
from tests.test_github_fabric_dispatch import admitted_children, operator_request
from tests.test_github_fabric_private_github import PrivateGitDataAPI

NEW_PARENT = "https://chatgpt.com/c/manual-new-parent-review-20261009"


class ManualNewParentGitHubRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.operator = operator_request()
        self.children = admitted_children()

    def inspect(self, api, *, source_kind, pinned_sha, **options):
        return manual.preview_manual_new_parent_from_github(
            self.operator, self.children,
            source_kind=source_kind,
            independently_pinned_source_sha=pinned_sha,
            destination_parent_conversation_url=NEW_PARENT,
            api=api, enabled=True, **options
        )

    def test_private_recovery_get_only_with_no_effect_authority(self):
        api = PrivateGitDataAPI()
        private_git.publish_private_synthetic_fixture(
            self.operator, self.children, enabled=True, api=api
        )
        head = api.head
        old_commits = len(api.commits)
        before = len(api.operations)
        result = self.inspect(api, source_kind=private_reader.SOURCE_KIND, pinned_sha=head)
        self.assertEqual(result.source_head_sha, head)
        self.assertEqual(result.source_kind, private_reader.SOURCE_KIND)
        self.assertEqual(result.decision, "manual_read_only_review")
        self.assertEqual(len(result.child_request_ids), 2)
        self.assertFalse(result.browser_effects_permitted)
        self.assertFalse(result.automatic_retry_permitted)
        self.assertFalse(result.legacy_worker_retirement_proven)
        self.assertEqual({entry[0] for entry in api.operations[before:]}, {"GET"})
        self.assertEqual(api.head, head)
        self.assertEqual(len(api.commits), old_commits)

    def test_public_recovery_get_only_with_no_effect_authority(self):
        api = AtomicGitDataAPI()
        public_git.publish_synthetic_fixture(
            self.operator, self.children, api=api, enabled=True
        )
        claims_writer.publish_synthetic_claims(
            self.operator, self.children, api=api, enabled=True
        )
        head = api.head
        old_commits = len(api.commits)
        before = len(api.operations)
        result = self.inspect(api, source_kind=public_reader.SOURCE_KIND, pinned_sha=head)
        self.assertEqual(result.source_head_sha, head)
        self.assertEqual(result.source_kind, public_reader.SOURCE_KIND)
        self.assertEqual(len(result.child_request_ids), 2)
        self.assertFalse(result.browser_effects_permitted)
        self.assertFalse(result.automatic_retry_permitted)
        self.assertEqual({entry[0] for entry in api.operations[before:]}, {"GET"})
        self.assertEqual(api.head, head)
        self.assertEqual(len(api.commits), old_commits)

    def test_default_disabled_and_bad_arguments_prevent_remote_io(self):
        api = PrivateGitDataAPI()
        kwargs = dict(
            source_kind=private_reader.SOURCE_KIND,
            independently_pinned_source_sha="a" * 40,
            destination_parent_conversation_url=NEW_PARENT,
            api=api,
        )
        with self.assertRaisesRegex(PermissionError, "default-disabled"):
            manual.preview_manual_new_parent_from_github(
                self.operator, self.children, **kwargs
            )
        self.assertEqual(api.operations, [])
        for update in (
            {"source_kind": "unknown"},
            {"independently_pinned_source_sha": "bad"},
            {"destination_parent_conversation_url":
             self.operator["parent_conversation_url"]},
            {"destination_parent_conversation_url": "https://evil.test/c/new-parent"},
            {"token": "ambiguous credential"},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                manual.preview_manual_new_parent_from_github(
                    self.operator, self.children, enabled=True,
                    **{**kwargs, **update}
                )
        self.assertEqual(api.operations, [])

    def test_pin_mismatch_after_read_does_not_emit_handoff(self):
        api = PrivateGitDataAPI()
        private_git.publish_private_synthetic_fixture(
            self.operator, self.children, enabled=True, api=api
        )
        before = len(api.operations)
        with self.assertRaisesRegex(ValueError, "source SHA"):
            self.inspect(
                api, source_kind=private_reader.SOURCE_KIND, pinned_sha="e" * 40
            )
        self.assertEqual({entry[0] for entry in api.operations[before:]}, {"GET"})

    def test_partial_remote_snapshot_fails_closed(self):
        private_api = PrivateGitDataAPI()
        with self.assertRaisesRegex(ValueError, "not fully indexed"):
            self.inspect(
                private_api, source_kind=private_reader.SOURCE_KIND,
                pinned_sha=private_api.head,
            )
        self.assertTrue(all(method == "GET" for method, *_ in private_api.operations))
        public_api = AtomicGitDataAPI()
        with self.assertRaisesRegex(ValueError, "dispatch index is missing"):
            self.inspect(
                public_api, source_kind=public_reader.SOURCE_KIND,
                pinned_sha=public_api.head,
            )
        self.assertTrue(all(method == "GET" for method, *_ in public_api.operations))

    def test_unapproved_private_input_fails_before_remote_io(self):
        api = PrivateGitDataAPI()
        self.children[0]["scope"]["summary"] = "PRIVATE UNAPPROVED PAYLOAD"
        with self.assertRaises(PermissionError):
            self.inspect(
                api, source_kind=private_reader.SOURCE_KIND, pinned_sha=api.head
            )
        self.assertEqual(api.operations, [])

    def test_get_only_guard_rejects_any_mutating_method_or_request_body(self):
        api = PrivateGitDataAPI()
        guard = manual._GetOnlyAPI(api)
        for method, body in (("POST", {}), ("PATCH", {"force": False}),
                             ("DELETE", None), ("GET", {})):
            with self.subTest(method=method, body=body), self.assertRaisesRegex(
                PermissionError, "forbids GitHub mutation"
            ):
                guard.request(method, "/git/commits/anything", body)
        self.assertEqual(api.operations, [])


if __name__ == "__main__":
    unittest.main()
