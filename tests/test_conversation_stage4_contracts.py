from __future__ import annotations

import copy
import unittest

from local_agent.conversation import bootstrap, contract, records, spawn, state


BINDING = "12345678-1234-4abc-8def-1234567890ab"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
CHILD_URL = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222"
INTRO_DIGEST = "sha256:" + "1" * 64
CONTEXT_DIGEST = "sha256:" + "2" * 64
COMMIT_SHA = "a" * 40


def valid_request() -> dict:
    return {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": "child-audit-001",
        "workflow_id": "audit-44",
        "workflow_node_id": "audit-node-01",
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": INTRO_DIGEST,
        "parent_conversation_url": PARENT_URL,
        "created_at": "2026-09-24T12:00:00Z",
        "role": "verification",
        "repository_id": "local-agent",
        "agent_binding": BINDING,
        "repository_ref": "develop/conversation-fabric",
        "repository_commit_sha": COMMIT_SHA,
        "scope": {
            "summary": "Verify one bounded Conversation Fabric contract slice.",
            "paths": ["local_agent/conversation/contract.py"],
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


def valid_registration(request: dict | None = None) -> dict:
    source = valid_request() if request is None else request
    return {
        "schema_version": contract.CHILD_REGISTRATION_SCHEMA_VERSION,
        "child_request_id": source["id"],
        "child_request_digest": contract.child_request_digest(source),
        "parent_conversation_url": source["parent_conversation_url"],
        "child_conversation_url": CHILD_URL,
        "registered_at": "2026-09-24T12:01:00Z",
    }


def provenance(request: dict) -> dict:
    return {
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "workflow_id": request["workflow_id"],
        "workflow_node_id": request["workflow_node_id"],
        "workflow_node_revision": request["workflow_node_revision"],
        "workflow_node_introduction_digest": request[
            "workflow_node_introduction_digest"
        ],
    }


def evidence_refs() -> list[dict]:
    return [
        {
            "kind": "git_commit",
            "repository_id": "local-agent",
            "commit_sha": "b" * 40,
        },
        {
            "kind": "local_agent_task_result",
            "repository_id": "local-agent",
            "agent_binding": BINDING,
            "task_id": "wf-" + "c" * 64,
            "task_digest": "d" * 64,
        },
        {
            "kind": "github_actions_run",
            "repository": "MichalMatu/local-agent",
            "run_id": 123456,
            "run_attempt": 1,
            "head_sha": "b" * 40,
        },
    ]


def checkpoint(request: dict) -> dict:
    return {
        "schema_version": records.CHILD_CHECKPOINT_SCHEMA_VERSION,
        **provenance(request),
        "sequence": 1,
        "summary": "Contract verification is in progress.",
        "evidence_refs": evidence_refs(),
        "recorded_at": "2026-09-24T12:10:00Z",
    }


def terminal(request: dict) -> dict:
    return {
        "schema_version": records.CHILD_TERMINAL_SCHEMA_VERSION,
        **provenance(request),
        "outcome": "succeeded",
        "summary": "The bounded reasoning child completed its scope.",
        "evidence_refs": evidence_refs(),
        "recorded_at": "2026-09-24T12:20:00Z",
    }


def advance_to_submit_boundary(request: dict, transaction: dict) -> dict:
    transaction = spawn.transition_spawn_transaction(
        transaction,
        request=request,
        target="tab_created",
        tab_id=41,
        updated_at="2026-09-24T12:02:01Z",
    )
    transaction = spawn.transition_spawn_transaction(
        transaction,
        request=request,
        target="bootstrap_ready",
        updated_at="2026-09-24T12:02:02Z",
    )
    return spawn.transition_spawn_transaction(
        transaction,
        request=request,
        target="bootstrap_submitting",
        updated_at="2026-09-24T12:02:03Z",
    )


class ChildRequestRegistrationTests(unittest.TestCase):
    def test_request_digest_is_canonical_and_excludes_created_at(self) -> None:
        request = valid_request()
        reordered = dict(reversed(list(request.items())))
        later = copy.deepcopy(request)
        later["created_at"] = "2026-09-24T13:00:00Z"
        contract.validate_child_request(request)
        self.assertEqual(
            contract.child_request_digest(request),
            contract.child_request_digest(reordered),
        )
        self.assertEqual(
            contract.child_request_digest(request),
            contract.child_request_digest(later),
        )
        self.assertRegex(contract.child_request_digest(request), r"^sha256:[0-9a-f]{64}$")

    def test_request_rejects_unknown_missing_and_noncanonical_authority(self) -> None:
        candidate = valid_request()
        candidate["campaign_id"] = "legacy"
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            contract.validate_child_request(candidate)

        candidate = valid_request()
        candidate.pop("workflow_id")
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            contract.validate_child_request(candidate)

        for field, value, message in (
            ("agent_binding", "not-a-binding", "agent_binding"),
            ("repository_ref", "../main", "repository_ref"),
            ("repository_commit_sha", "A" * 40, "commit SHA"),
            ("parent_conversation_url", "https://example.com/c/x", "ChatGPT origin"),
        ):
            candidate = valid_request()
            candidate[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, message):
                    contract.validate_child_request(candidate)

    def test_request_scope_and_context_are_bounded_canonical_inputs(self) -> None:
        for bad_path in ("/absolute", "../escape", "a//b", "a\\b"):
            candidate = valid_request()
            candidate["scope"]["paths"] = [bad_path]
            with self.subTest(path=bad_path):
                with self.assertRaisesRegex(ValueError, "scope paths"):
                    contract.validate_child_request(candidate)

        candidate = valid_request()
        candidate["scope"]["paths"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            contract.validate_child_request(candidate)

        candidate = valid_request()
        candidate["context_refs"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            contract.validate_child_request(candidate)

    def test_request_target_and_workflow_provenance_fail_closed(self) -> None:
        request = valid_request()
        contract.require_child_request_target(
            request,
            repository_id="local-agent",
            agent_binding=BINDING,
        )
        contract.require_child_request_workflow_provenance(
            request,
            workflow_id="audit-44",
            workflow_node_id="audit-node-01",
            workflow_node_revision=0,
            workflow_node_introduction_digest=INTRO_DIGEST,
        )

        with self.assertRaisesRegex(ValueError, "repository mismatch"):
            contract.require_child_request_target(
                request,
                repository_id="other-repo",
                agent_binding=BINDING,
            )
        with self.assertRaisesRegex(ValueError, "workflow_node_revision mismatch"):
            contract.require_child_request_workflow_provenance(
                request,
                workflow_id="audit-44",
                workflow_node_id="audit-node-01",
                workflow_node_revision=1,
                workflow_node_introduction_digest=INTRO_DIGEST,
            )

    def test_registration_is_create_once_and_conflicting_url_fails(self) -> None:
        request = valid_request()
        registration = valid_registration(request)
        contract.validate_child_registration(registration, request=request)
        self.assertEqual(
            contract.reconcile_child_registration(None, registration, request=request),
            registration,
        )
        duplicate = copy.deepcopy(registration)
        duplicate["registered_at"] = "2026-09-24T12:05:00Z"
        self.assertEqual(
            contract.reconcile_child_registration(registration, duplicate, request=request),
            registration,
        )

        conflict = copy.deepcopy(registration)
        conflict["child_conversation_url"] = (
            "https://chatgpt.com/c/33333333-3333-4333-8333-333333333333"
        )
        with self.assertRaisesRegex(ValueError, "conflicting child conversation URL"):
            contract.reconcile_child_registration(registration, conflict, request=request)

    def test_registration_requires_canonical_distinct_child_identity(self) -> None:
        request = valid_request()
        candidate = valid_registration(request)
        candidate["child_conversation_url"] = request["parent_conversation_url"]
        with self.assertRaisesRegex(ValueError, "must differ"):
            contract.validate_child_registration(candidate, request=request)

        candidate = valid_registration(request)
        candidate["child_conversation_url"] = CHILD_URL + "?x=1"
        with self.assertRaisesRegex(ValueError, "query or fragment"):
            contract.validate_child_registration(candidate, request=request)


class ChildBootstrapLifecycleTests(unittest.TestCase):
    def test_bootstrap_is_deterministic_bounded_and_pinned_to_request(self) -> None:
        request = valid_request()
        first = bootstrap.child_bootstrap_message(request)
        second = bootstrap.child_bootstrap_message(copy.deepcopy(request))
        self.assertEqual(first, second)
        self.assertIn("LOCAL AGENT CHILD BOOTSTRAP", first)
        digest = bootstrap.child_bootstrap_digest(request)
        bootstrap.require_child_bootstrap_digest(request, expected_digest=digest)
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            bootstrap.require_child_bootstrap_digest(
                request,
                expected_digest="sha256:" + "0" * 64,
            )

    def test_logical_lifecycle_is_monotonic_with_explicit_cancel_abandon(self) -> None:
        current = state.initial_child_state()
        for target in (
            "registration_pending",
            "active",
            "terminal_pending_evidence",
            "terminal_recorded",
            "retired",
        ):
            current = state.transition_child_state(current, target)
        self.assertEqual(current, "retired")

        self.assertEqual(
            state.transition_child_state("requested", "cancelled"), "cancelled"
        )
        self.assertEqual(
            state.transition_child_state("active", "abandoned"), "abandoned"
        )
        with self.assertRaisesRegex(ValueError, "invalid child lifecycle transition"):
            state.transition_child_state("requested", "active")
        with self.assertRaisesRegex(ValueError, "invalid child lifecycle transition"):
            state.transition_child_state("terminal_recorded", "cancelled")


class ChildEvidenceRecordTests(unittest.TestCase):
    def test_checkpoint_and_terminal_validate_and_have_stable_semantic_digests(self) -> None:
        request = valid_request()
        candidate_checkpoint = checkpoint(request)
        candidate_terminal = terminal(request)
        records.validate_child_checkpoint(candidate_checkpoint, request=request)
        records.validate_child_terminal(candidate_terminal, request=request)

        later_checkpoint = copy.deepcopy(candidate_checkpoint)
        later_checkpoint["recorded_at"] = "2026-09-24T12:11:00Z"
        self.assertEqual(
            records.child_checkpoint_digest(candidate_checkpoint, request=request),
            records.child_checkpoint_digest(later_checkpoint, request=request),
        )
        later_terminal = copy.deepcopy(candidate_terminal)
        later_terminal["recorded_at"] = "2026-09-24T12:21:00Z"
        self.assertEqual(
            records.child_terminal_digest(candidate_terminal, request=request),
            records.child_terminal_digest(later_terminal, request=request),
        )

    def test_evidence_provenance_and_types_fail_closed(self) -> None:
        request = valid_request()
        candidate = checkpoint(request)
        candidate["workflow_node_revision"] = 1
        with self.assertRaisesRegex(ValueError, "does not match child request"):
            records.validate_child_checkpoint(candidate, request=request)

        candidate = terminal(request)
        candidate["evidence_refs"] = [
            {"kind": "model_assertion", "id": "tests-passed", "verified": True}
        ]
        with self.assertRaisesRegex(ValueError, "unsupported evidence reference kind"):
            records.validate_child_terminal(candidate, request=request)

        candidate = checkpoint(request)
        duplicate = evidence_refs()[0]
        candidate["evidence_refs"] = [duplicate, copy.deepcopy(duplicate)]
        with self.assertRaisesRegex(ValueError, "duplicates"):
            records.validate_child_checkpoint(candidate, request=request)

    def test_reasoning_terminal_may_have_no_execution_evidence(self) -> None:
        request = valid_request()
        candidate = terminal(request)
        candidate["evidence_refs"] = []
        records.validate_child_terminal(candidate, request=request)


class SpawnTransactionContractTests(unittest.TestCase):
    def test_spawn_identity_is_attempt_scoped_and_not_tab_scoped(self) -> None:
        request = valid_request()
        first = spawn.build_spawn_transaction(
            request,
            attempt=1,
            created_at="2026-09-24T12:02:00Z",
        )
        retry_same_attempt = spawn.build_spawn_transaction(
            copy.deepcopy(request),
            attempt=1,
            created_at="2026-09-24T12:03:00Z",
        )
        second_attempt = spawn.build_spawn_transaction(
            request,
            attempt=2,
            created_at="2026-09-24T12:04:00Z",
        )
        self.assertEqual(first["id"], retry_same_attempt["id"])
        self.assertNotEqual(first["id"], second_attempt["id"])

        with_tab = spawn.transition_spawn_transaction(
            first,
            request=request,
            target="tab_created",
            tab_id=41,
            updated_at="2026-09-24T12:02:01Z",
        )
        cleared = spawn.clear_spawn_tab_cache(
            with_tab,
            request=request,
            updated_at="2026-09-24T12:02:02Z",
        )
        self.assertEqual(cleared["id"], first["id"])
        self.assertIsNone(cleared["tab_id"])

    def test_spawn_happy_path_requires_identity_after_submit_boundary(self) -> None:
        request = valid_request()
        transaction = spawn.build_spawn_transaction(
            request,
            attempt=1,
            created_at="2026-09-24T12:02:00Z",
        )
        transaction = advance_to_submit_boundary(request, transaction)
        transaction = spawn.transition_spawn_transaction(
            transaction,
            request=request,
            target="identity_discovered",
            child_conversation_url=CHILD_URL,
            updated_at="2026-09-24T12:02:04Z",
        )
        transaction = spawn.transition_spawn_transaction(
            transaction,
            request=request,
            target="registration_submitting",
            updated_at="2026-09-24T12:02:05Z",
        )
        transaction = spawn.transition_spawn_transaction(
            transaction,
            request=request,
            target="done",
            updated_at="2026-09-24T12:02:06Z",
        )
        self.assertEqual(transaction["state"], "done")
        self.assertEqual(transaction["child_conversation_url"], CHILD_URL)

    def test_pre_submit_failure_is_retryable_but_post_submit_uncertainty_is_ambiguous(self) -> None:
        request = valid_request()
        pending = spawn.build_spawn_transaction(
            request,
            attempt=1,
            created_at="2026-09-24T12:02:00Z",
        )
        failed = spawn.fail_spawn_transaction(
            pending,
            request=request,
            reason="safe failure before submission",
            updated_at="2026-09-24T12:02:01Z",
        )
        self.assertEqual(failed["state"], "failed")

        submitting = advance_to_submit_boundary(
            request,
            spawn.build_spawn_transaction(
                request,
                attempt=2,
                created_at="2026-09-24T12:02:00Z",
            ),
        )
        ambiguous = spawn.fail_spawn_transaction(
            submitting,
            request=request,
            reason="submission acknowledgement lost",
            updated_at="2026-09-24T12:02:04Z",
        )
        self.assertEqual(ambiguous["state"], "ambiguous")

    def test_spawn_cancellation_and_invalid_replay_fail_closed(self) -> None:
        request = valid_request()
        pending = spawn.build_spawn_transaction(
            request,
            attempt=1,
            created_at="2026-09-24T12:02:00Z",
        )
        cancelled = spawn.cancel_spawn_transaction(
            pending,
            request=request,
            reason="operator cancelled before submission",
            updated_at="2026-09-24T12:02:01Z",
        )
        self.assertEqual(cancelled["state"], "cancelled")
        with self.assertRaisesRegex(ValueError, "terminal spawn transaction"):
            spawn.fail_spawn_transaction(
                cancelled,
                request=request,
                reason="cannot replay terminal attempt",
                updated_at="2026-09-24T12:02:02Z",
            )

        with self.assertRaisesRegex(ValueError, "invalid spawn transaction transition"):
            spawn.transition_spawn_transaction(
                pending,
                request=request,
                target="identity_discovered",
                child_conversation_url=CHILD_URL,
                updated_at="2026-09-24T12:02:01Z",
            )

    def test_spawn_is_pinned_to_exact_request_bootstrap_and_child_url(self) -> None:
        request = valid_request()
        transaction = spawn.build_spawn_transaction(
            request,
            attempt=1,
            created_at="2026-09-24T12:02:00Z",
        )
        changed_request = copy.deepcopy(request)
        changed_request["repository_commit_sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "transaction id does not match"):
            spawn.validate_spawn_transaction(transaction, request=changed_request)

        tampered = copy.deepcopy(transaction)
        tampered["bootstrap_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            spawn.validate_spawn_transaction(tampered, request=request)

        submitting = advance_to_submit_boundary(request, transaction)
        with self.assertRaisesRegex(ValueError, "must differ from parent"):
            spawn.transition_spawn_transaction(
                submitting,
                request=request,
                target="identity_discovered",
                child_conversation_url=PARENT_URL,
                updated_at="2026-09-24T12:02:04Z",
            )


if __name__ == "__main__":
    unittest.main()
