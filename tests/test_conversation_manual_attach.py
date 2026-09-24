from __future__ import annotations

import copy
import unittest

from local_agent.conversation import bootstrap, contract, manual_attach


AGENT_BINDING = "12345678-1234-4abc-8def-1234567890ab"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
CHILD_URL = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222"
WORKFLOW_DIGEST = "sha256:" + "1" * 64
CONTEXT_DIGEST = "sha256:" + "2" * 64
REPOSITORY_COMMIT = "a" * 40


def valid_request() -> dict:
    return {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": "child-audit-001",
        "workflow_id": "audit-44",
        "workflow_node_id": "audit-node-01",
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": WORKFLOW_DIGEST,
        "parent_conversation_url": PARENT_URL,
        "created_at": "2026-09-23T20:00:00Z",
        "role": "research",
        "repository_id": "local-agent",
        "agent_binding": AGENT_BINDING,
        "repository_ref": "develop/conversation-fabric",
        "repository_commit_sha": REPOSITORY_COMMIT,
        "scope": {
            "summary": "Audit one bounded module.",
            "paths": ["local_agent/conversation"],
        },
        "context_refs": [
            {
                "kind": "finding",
                "id": "finding-001",
                "digest": CONTEXT_DIGEST,
            }
        ],
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }


class ManualAttachContractTests(unittest.TestCase):
    def test_intent_derives_authority_only_from_admitted_request(self) -> None:
        request = valid_request()
        digest = bootstrap.child_bootstrap_digest(request)
        intent = manual_attach.build_manual_attach_intent(
            request,
            child_conversation_url=CHILD_URL,
            submitted_bootstrap_digest=digest,
        )

        self.assertEqual(intent["child_request_id"], request["id"])
        self.assertEqual(
            intent["child_request_digest"],
            contract.child_request_digest(request),
        )
        self.assertEqual(intent["workflow_id"], request["workflow_id"])
        self.assertEqual(intent["workflow_node_id"], request["workflow_node_id"])
        self.assertEqual(intent["repository_id"], request["repository_id"])
        self.assertEqual(intent["agent_binding"], request["agent_binding"])
        self.assertEqual(intent["bootstrap_digest"], digest)
        self.assertEqual(intent["child_conversation_url"], CHILD_URL)
        manual_attach.validate_manual_attach_intent(intent, request=request)

    def test_builder_normalizes_observed_child_url_but_validator_requires_canonical(self) -> None:
        request = valid_request()
        digest = bootstrap.child_bootstrap_digest(request)
        intent = manual_attach.build_manual_attach_intent(
            request,
            child_conversation_url=CHILD_URL.replace("chatgpt.com", "chat.openai.com") + "/",
            submitted_bootstrap_digest=digest,
        )
        self.assertEqual(intent["child_conversation_url"], CHILD_URL)

        tampered = copy.deepcopy(intent)
        tampered["child_conversation_url"] = CHILD_URL + "/"
        with self.assertRaisesRegex(ValueError, "canonical ChatGPT form"):
            manual_attach.validate_manual_attach_intent(tampered, request=request)

    def test_wrong_bootstrap_digest_fails_closed(self) -> None:
        request = valid_request()
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            manual_attach.build_manual_attach_intent(
                request,
                child_conversation_url=CHILD_URL,
                submitted_bootstrap_digest="sha256:" + "0" * 64,
            )

    def test_parent_cannot_be_attached_as_its_own_child(self) -> None:
        request = valid_request()
        with self.assertRaisesRegex(ValueError, "must differ from parent"):
            manual_attach.build_manual_attach_intent(
                request,
                child_conversation_url=PARENT_URL,
                submitted_bootstrap_digest=bootstrap.child_bootstrap_digest(request),
            )

    def test_browser_side_authority_tampering_is_rejected(self) -> None:
        request = valid_request()
        intent = manual_attach.build_manual_attach_intent(
            request,
            child_conversation_url=CHILD_URL,
            submitted_bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        cases = (
            ("repository_id", "other-repo"),
            ("agent_binding", "87654321-4321-4abc-8def-1234567890ab"),
            ("workflow_id", "other-workflow"),
            ("workflow_node_id", "other-node"),
            ("workflow_node_revision", 1),
            ("workflow_node_introduction_digest", "sha256:" + "3" * 64),
        )
        for field, value in cases:
            tampered = copy.deepcopy(intent)
            tampered[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "does not match admitted request"):
                    manual_attach.validate_manual_attach_intent(
                        tampered,
                        request=request,
                    )

    def test_created_at_does_not_change_manual_attach_identity(self) -> None:
        request = valid_request()
        later = copy.deepcopy(request)
        later["created_at"] = "2026-09-23T21:00:00Z"
        first = manual_attach.build_manual_attach_intent(
            request,
            child_conversation_url=CHILD_URL,
            submitted_bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        second = manual_attach.build_manual_attach_intent(
            later,
            child_conversation_url=CHILD_URL,
            submitted_bootstrap_digest=bootstrap.child_bootstrap_digest(later),
        )
        self.assertEqual(first, second)
        self.assertEqual(
            manual_attach.manual_attach_digest(first, request=request),
            manual_attach.manual_attach_digest(second, request=later),
        )

    def test_reconcile_is_idempotent_and_rejects_second_child(self) -> None:
        request = valid_request()
        intent = manual_attach.build_manual_attach_intent(
            request,
            child_conversation_url=CHILD_URL,
            submitted_bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        self.assertEqual(
            manual_attach.reconcile_manual_attach_intent(
                intent,
                copy.deepcopy(intent),
                request=request,
            ),
            intent,
        )

        other = copy.deepcopy(intent)
        other["child_conversation_url"] = (
            "https://chatgpt.com/c/33333333-3333-4333-8333-333333333333"
        )
        with self.assertRaisesRegex(ValueError, "conflicting manual attach intent"):
            manual_attach.reconcile_manual_attach_intent(
                intent,
                other,
                request=request,
            )

    def test_registration_is_derived_from_validated_attach_intent(self) -> None:
        request = valid_request()
        intent = manual_attach.build_manual_attach_intent(
            request,
            child_conversation_url=CHILD_URL,
            submitted_bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        registration = manual_attach.registration_from_manual_attach(
            intent,
            request=request,
            registered_at="2026-09-23T20:05:00Z",
        )
        contract.validate_child_registration(registration, request=request)
        self.assertEqual(registration["child_conversation_url"], CHILD_URL)
        self.assertEqual(registration["child_request_id"], request["id"])

    def test_intent_rejects_unknown_fields(self) -> None:
        request = valid_request()
        intent = manual_attach.build_manual_attach_intent(
            request,
            child_conversation_url=CHILD_URL,
            submitted_bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        intent["preferred_tab_id"] = 17
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            manual_attach.validate_manual_attach_intent(intent, request=request)


if __name__ == "__main__":
    unittest.main()
