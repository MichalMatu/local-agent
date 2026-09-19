from __future__ import annotations

import unittest

from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import evidence


TASK_ID = "wf-" + "a" * 64


def child_task(command: str = "true") -> dict:
    return {
        "id": TASK_ID,
        "agent_binding": "00000000-0000-4000-8000-000000000071",
        "resources": [],
        "commands": [command],
    }


class WorkflowEvidenceTests(unittest.TestCase):
    def test_absent_without_task_status_or_result(self) -> None:
        task = child_task()
        observed = evidence.classify_child_evidence(
            task_payload=None,
            status_payload=None,
            result_payload=None,
            expected_task_id=TASK_ID,
            expected_digest=task_digest(task),
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.ABSENT)

    def test_exact_task_without_terminal_evidence_is_pending(self) -> None:
        task = child_task()
        digest = task_digest(task)
        observed = evidence.classify_child_evidence(
            task_payload=task,
            status_payload={"state": "idle"},
            result_payload=None,
            expected_task_id=TASK_ID,
            expected_digest=digest,
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.PENDING)
        self.assertEqual(observed.task_digest, digest)

    def test_exact_running_status_is_authoritative(self) -> None:
        task = child_task()
        digest = task_digest(task)
        observed = evidence.classify_child_evidence(
            task_payload=None,
            status_payload={
                "state": "running",
                "current_task_id": TASK_ID,
                "current_task_digest": digest,
            },
            result_payload=None,
            expected_task_id=TASK_ID,
            expected_digest=digest,
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.RUNNING)
        self.assertEqual(observed.task_digest, digest)

    def test_terminal_done_result_is_success(self) -> None:
        task = child_task()
        digest = task_digest(task)
        observed = evidence.classify_child_evidence(
            task_payload=task,
            status_payload=None,
            result_payload={"id": TASK_ID, "status": "done", "task_digest": digest},
            expected_task_id=TASK_ID,
            expected_digest=digest,
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.SUCCEEDED)

    def test_terminal_failure_is_failed(self) -> None:
        task = child_task()
        digest = task_digest(task)
        observed = evidence.classify_child_evidence(
            task_payload=task,
            status_payload=None,
            result_payload={
                "id": TASK_ID,
                "status": "failed",
                "task_digest": digest,
                "failure_reason": "command_failed",
            },
            expected_task_id=TASK_ID,
            expected_digest=digest,
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.FAILED)
        self.assertEqual(observed.failure_reason, "command_failed")

    def test_no_replay_failures_are_interrupted(self) -> None:
        task = child_task()
        digest = task_digest(task)
        for reason in ("interrupted_previous_attempt", "corrupt_claim_state"):
            with self.subTest(reason=reason):
                observed = evidence.classify_child_evidence(
                    task_payload=task,
                    status_payload=None,
                    result_payload={
                        "id": TASK_ID,
                        "status": "failed",
                        "task_digest": digest,
                        "failure_reason": reason,
                    },
                    expected_task_id=TASK_ID,
                    expected_digest=digest,
                )
                self.assertEqual(observed.kind, evidence.ChildEvidenceKind.INTERRUPTED)

    def test_operator_cancel_is_distinct_terminal_evidence(self) -> None:
        task = child_task()
        digest = task_digest(task)
        observed = evidence.classify_child_evidence(
            task_payload=task,
            status_payload=None,
            result_payload={
                "id": TASK_ID,
                "status": "failed",
                "task_digest": digest,
                "failure_reason": "cancelled_by_operator",
            },
            expected_task_id=TASK_ID,
            expected_digest=digest,
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.CANCELLED)

    def test_task_payload_digest_mismatch_is_fail_closed(self) -> None:
        expected = child_task()
        conflicting = child_task("false")
        observed = evidence.classify_child_evidence(
            task_payload=conflicting,
            status_payload=None,
            result_payload=None,
            expected_task_id=TASK_ID,
            expected_digest=task_digest(expected),
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.DIGEST_MISMATCH)
        self.assertEqual(observed.task_digest, task_digest(conflicting))

    def test_terminal_result_digest_mismatch_is_fail_closed(self) -> None:
        task = child_task()
        observed = evidence.classify_child_evidence(
            task_payload=task,
            status_payload=None,
            result_payload={
                "id": TASK_ID,
                "status": "done",
                "task_digest": "0" * 64,
            },
            expected_task_id=TASK_ID,
            expected_digest=task_digest(task),
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.DIGEST_MISMATCH)

    def test_running_status_digest_mismatch_is_fail_closed(self) -> None:
        task = child_task()
        observed = evidence.classify_child_evidence(
            task_payload=task,
            status_payload={
                "state": "running",
                "current_task_id": TASK_ID,
                "current_task_digest": "0" * 64,
            },
            result_payload=None,
            expected_task_id=TASK_ID,
            expected_digest=task_digest(task),
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.DIGEST_MISMATCH)

    def test_unrelated_active_or_pending_work_blocks_dispatch(self) -> None:
        child = child_task()
        other = {
            "id": "standalone-task",
            "agent_binding": child["agent_binding"],
            "resources": [],
            "commands": ["true"],
        }
        self.assertTrue(
            evidence.has_unrelated_work(
                child_task_id=TASK_ID,
                status_payload={"current_task_id": "standalone-task"},
                task_payloads=[child],
                result_payloads={},
            )
        )
        self.assertTrue(
            evidence.has_unrelated_work(
                child_task_id=TASK_ID,
                status_payload={"pending_task_id": "standalone-task"},
                task_payloads=[child],
                result_payloads={},
            )
        )
        self.assertTrue(
            evidence.has_unrelated_work(
                child_task_id=TASK_ID,
                status_payload={},
                task_payloads=[child, other],
                result_payloads={},
            )
        )

    def test_completed_unrelated_task_does_not_block_dispatch(self) -> None:
        child = child_task()
        other = {
            "id": "standalone-task",
            "agent_binding": child["agent_binding"],
            "resources": [],
            "commands": ["true"],
        }
        self.assertFalse(
            evidence.has_unrelated_work(
                child_task_id=TASK_ID,
                status_payload={},
                task_payloads=[child, other],
                result_payloads={"standalone-task": {"id": "standalone-task", "status": "done"}},
            )
        )


if __name__ == "__main__":
    unittest.main()
