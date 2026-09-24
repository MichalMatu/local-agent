from __future__ import annotations

import copy
import unittest

from local_agent.conversation import adoption, bootstrap, contract


AGENT_BINDING = "12345678-1234-4abc-8def-1234567890ab"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
CHILD_URL = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222"
WORKFLOW_DIGEST = "sha256:" + "1" * 64


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
        "role": "verification",
        "repository_id": "local-agent",
        "agent_binding": AGENT_BINDING,
        "repository_ref": "main",
        "repository_commit_sha": "a" * 40,
        "scope": {"summary": "Verify the bounded result.", "paths": ["local_agent"]},
        "context_refs": [],
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }


def valid_registration(request: dict) -> dict:
    return {
        "schema_version": contract.CHILD_REGISTRATION_SCHEMA_VERSION,
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "parent_conversation_url": request["parent_conversation_url"],
        "child_conversation_url": CHILD_URL,
        "registered_at": "2026-09-23T20:05:00Z",
    }


class BridgeAdoptionAuthorityTests(unittest.TestCase):
    def test_authority_is_minimal_and_derived_from_durable_records(self) -> None:
        request = valid_request()
        registration = valid_registration(request)
        authority = adoption.build_bridge_adoption_authority(
            request,
            registration,
            bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        self.assertEqual(
            set(authority),
            {
                "schema_version",
                "child_request_id",
                "child_request_digest",
                "child_conversation_url",
                "repository_id",
                "agent_binding",
                "bootstrap_digest",
            },
        )
        self.assertEqual(authority["child_conversation_url"], CHILD_URL)
        self.assertEqual(authority["repository_id"], request["repository_id"])
        self.assertEqual(authority["agent_binding"], request["agent_binding"])
        adoption.validate_bridge_adoption_authority(
            authority,
            request=request,
            registration=registration,
        )

    def test_registration_timestamp_does_not_change_adoption_authority(self) -> None:
        request = valid_request()
        registration = valid_registration(request)
        retry = copy.deepcopy(registration)
        retry["registered_at"] = "2026-09-23T20:06:00Z"
        first = adoption.build_bridge_adoption_authority(
            request,
            registration,
            bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        second = adoption.build_bridge_adoption_authority(
            request,
            retry,
            bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        self.assertEqual(first, second)

    def test_tampering_with_url_repository_binding_or_request_fails_closed(self) -> None:
        request = valid_request()
        registration = valid_registration(request)
        authority = adoption.build_bridge_adoption_authority(
            request,
            registration,
            bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        cases = (
            ("child_request_id", "other-request"),
            ("child_request_digest", "sha256:" + "0" * 64),
            (
                "child_conversation_url",
                "https://chatgpt.com/c/33333333-3333-4333-8333-333333333333",
            ),
            ("repository_id", "other-repo"),
            ("agent_binding", "87654321-4321-4abc-8def-1234567890ab"),
        )
        for field, value in cases:
            tampered = copy.deepcopy(authority)
            tampered[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "does not match durable authority"):
                    adoption.validate_bridge_adoption_authority(
                        tampered,
                        request=request,
                        registration=registration,
                    )

    def test_wrong_bootstrap_digest_is_rejected(self) -> None:
        request = valid_request()
        registration = valid_registration(request)
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            adoption.build_bridge_adoption_authority(
                request,
                registration,
                bootstrap_digest="sha256:" + "0" * 64,
            )

    def test_unknown_authority_fields_are_rejected(self) -> None:
        request = valid_request()
        registration = valid_registration(request)
        authority = adoption.build_bridge_adoption_authority(
            request,
            registration,
            bootstrap_digest=bootstrap.child_bootstrap_digest(request),
        )
        authority["preferred_tab_id"] = 17
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            adoption.validate_bridge_adoption_authority(
                authority,
                request=request,
                registration=registration,
            )


if __name__ == "__main__":
    unittest.main()
