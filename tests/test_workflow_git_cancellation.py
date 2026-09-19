from __future__ import annotations

import unittest

from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import evidence
from local_agent.workflow.git_cancellation import (
    CancelRequestState,
    GitWorkflowCancellationTransport,
    cancel_control_id,
)
from local_agent.workflow.git_control_plane import WorkflowGitIntegrityError
from tests.test_workflow_git_control_plane import (
    LostPushResponseControlPlane,
    WorkflowGitControlPlaneTests,
    publish_from_seed,
    remote_commit_count,
    remote_json,
    run_git,
    workflow_task,
)


class WorkflowGitCancellationTests(WorkflowGitControlPlaneTests):
    def setUp(self) -> None:
        super().setUp()
        self.cancellation = GitWorkflowCancellationTransport(self.control)

    def _queue_child(self) -> tuple[dict, str]:
        task = workflow_task("repo-a")
        self.control.publish_child(self.repo_a, task)
        return task, task_digest(task)

    def _sync_seed(self) -> None:
        run_git(self.seed_a, "pull", "--rebase", "origin", "agent-control")

    def _publish_ack(
        self,
        *,
        control_id: str,
        task_id: str,
        status: str,
        result: str,
    ) -> dict:
        self._sync_seed()
        payload = {
            "id": control_id,
            "action": "cancel_task",
            "status": status,
            "task_id": task_id,
            "result": result,
        }
        publish_from_seed(
            self.seed_a,
            f".agent/daemon/acks/{control_id}.json",
            payload,
            f"Publish cancellation ACK {status}",
        )
        return payload

    def test_cancel_control_id_is_deterministic_and_digest_bound(self) -> None:
        task = workflow_task("repo-a")
        digest = task_digest(task)
        first = cancel_control_id(self.repo_a.repository_id, str(task["id"]), digest)
        second = cancel_control_id(self.repo_a.repository_id, str(task["id"]), digest)
        changed = cancel_control_id(
            self.repo_a.repository_id,
            str(task["id"]),
            task_digest(workflow_task("repo-a", command="false")),
        )
        other_repo = cancel_control_id("repo-b", str(task["id"]), digest)

        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)
        self.assertNotEqual(first, other_repo)
        self.assertRegex(first, r"^wf-cancel-[0-9a-f]{64}$")

    def test_request_publishes_existing_cancel_task_protocol_and_retry_is_idempotent(self) -> None:
        task, digest = self._queue_child()
        before = remote_commit_count(self.origin_a)

        requested = self.cancellation.request_cancel(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self.assertEqual(requested.state, CancelRequestState.REQUESTED)
        self.assertEqual(remote_commit_count(self.origin_a), before + 1)
        self.assertEqual(
            remote_json(self.origin_a, "agent-control", ".agent/daemon/control.json"),
            {
                "id": requested.control_id,
                "action": "cancel_task",
                "task_id": task["id"],
            },
        )

        retried = self.cancellation.request_cancel(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self.assertEqual(retried.state, CancelRequestState.REQUESTED)
        self.assertEqual(retried.control_id, requested.control_id)
        self.assertEqual(remote_commit_count(self.origin_a), before + 1)

    def test_accepted_ack_is_reported_but_does_not_make_child_terminal(self) -> None:
        task, digest = self._queue_child()
        requested = self.cancellation.request_cancel(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        ack = self._publish_ack(
            control_id=requested.control_id,
            task_id=str(task["id"]),
            status="accepted",
            result="terminating_active_task",
        )

        observed = self.cancellation.inspect(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self.assertEqual(observed.state, CancelRequestState.ACCEPTED)
        self.assertEqual(observed.ack, ack)

        child = self.control.inspect_child(self.repo_a, str(task["id"]), digest)
        self.assertEqual(child.kind, evidence.ChildEvidenceKind.PENDING)

    def test_terminal_cancel_result_is_not_inferred_from_ack(self) -> None:
        task, digest = self._queue_child()
        requested = self.cancellation.request_cancel(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self._publish_ack(
            control_id=requested.control_id,
            task_id=str(task["id"]),
            status="completed",
            result="cancelled_before_execution",
        )

        control_evidence = self.cancellation.inspect(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self.assertEqual(control_evidence.state, CancelRequestState.COMPLETED)
        self.assertEqual(
            self.control.inspect_child(self.repo_a, str(task["id"]), digest).kind,
            evidence.ChildEvidenceKind.PENDING,
        )

        self._sync_seed()
        publish_from_seed(
            self.seed_a,
            f".agent/results/{task['id']}.json",
            {
                "id": task["id"],
                "status": "failed",
                "failure_reason": "cancelled_by_operator",
                "task_digest": digest,
            },
            "Publish terminal workflow cancellation result",
        )
        self.assertEqual(
            self.control.inspect_child(self.repo_a, str(task["id"]), digest).kind,
            evidence.ChildEvidenceKind.CANCELLED,
        )

    def test_terminal_child_before_request_returns_not_needed_without_control_commit(self) -> None:
        task, digest = self._queue_child()
        self._sync_seed()
        publish_from_seed(
            self.seed_a,
            f".agent/results/{task['id']}.json",
            {
                "id": task["id"],
                "status": "done",
                "task_digest": digest,
            },
            "Complete workflow child before cancellation",
        )
        before = remote_commit_count(self.origin_a)

        result = self.cancellation.request_cancel(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self.assertEqual(result.state, CancelRequestState.NOT_NEEDED)
        self.assertEqual(remote_commit_count(self.origin_a), before)
        self.assertIsNone(
            remote_json(self.origin_a, "agent-control", ".agent/daemon/control.json")
        )

    def test_missing_or_mismatched_child_is_never_cancelled(self) -> None:
        task = workflow_task("repo-a")
        digest = task_digest(task)
        with self.assertRaisesRegex(WorkflowGitIntegrityError, "missing task evidence"):
            self.cancellation.request_cancel(
                self.repo_a,
                str(task["id"]),
                digest,
            )

        conflicting = workflow_task("repo-a", command="false")
        publish_from_seed(
            self.seed_a,
            f".agent/tasks/{task['id']}.json",
            conflicting,
            "Publish conflicting workflow child",
        )
        with self.assertRaisesRegex(WorkflowGitIntegrityError, "mismatched task evidence"):
            self.cancellation.request_cancel(
                self.repo_a,
                str(task["id"]),
                digest,
            )

    def test_unacknowledged_existing_control_request_defers_without_overwrite(self) -> None:
        task, digest = self._queue_child()
        self._sync_seed()
        existing = {
            "id": "manual-status-request",
            "action": "status",
        }
        publish_from_seed(
            self.seed_a,
            ".agent/daemon/control.json",
            existing,
            "Publish unrelated unacknowledged control request",
        )

        deferred = self.cancellation.request_cancel(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self.assertEqual(deferred.state, CancelRequestState.DEFERRED)
        self.assertEqual(
            remote_json(self.origin_a, "agent-control", ".agent/daemon/control.json"),
            existing,
        )

    def test_acknowledged_existing_control_request_can_be_replaced(self) -> None:
        task, digest = self._queue_child()
        self._sync_seed()
        existing = {
            "id": "manual-status-request",
            "action": "status",
        }
        publish_from_seed(
            self.seed_a,
            ".agent/daemon/control.json",
            existing,
            "Publish acknowledged prior control request",
        )
        self._sync_seed()
        publish_from_seed(
            self.seed_a,
            ".agent/daemon/acks/manual-status-request.json",
            {
                "id": "manual-status-request",
                "action": "status",
                "status": "completed",
            },
            "Acknowledge prior control request",
        )

        requested = self.cancellation.request_cancel(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self.assertEqual(requested.state, CancelRequestState.REQUESTED)
        self.assertEqual(
            remote_json(self.origin_a, "agent-control", ".agent/daemon/control.json"),
            {
                "id": requested.control_id,
                "action": "cancel_task",
                "task_id": task["id"],
            },
        )

    def test_lost_push_response_is_proven_without_duplicate_cancel_commit(self) -> None:
        task, digest = self._queue_child()
        lost = LostPushResponseControlPlane(
            origin_url_for=lambda repository: self.origins[repository.repository_id]
        )
        transport = GitWorkflowCancellationTransport(lost)
        before = remote_commit_count(self.origin_a)

        requested = transport.request_cancel(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self.assertEqual(requested.state, CancelRequestState.REQUESTED)
        self.assertEqual(remote_commit_count(self.origin_a), before + 1)
        self.assertEqual(
            remote_json(self.origin_a, "agent-control", ".agent/daemon/control.json"),
            {
                "id": requested.control_id,
                "action": "cancel_task",
                "task_id": task["id"],
            },
        )

        transport.request_cancel(self.repo_a, str(task["id"]), digest)
        self.assertEqual(remote_commit_count(self.origin_a), before + 1)

    def test_malformed_exact_ack_fails_closed(self) -> None:
        task, digest = self._queue_child()
        requested = self.cancellation.request_cancel(
            self.repo_a,
            str(task["id"]),
            digest,
        )
        self._sync_seed()
        publish_from_seed(
            self.seed_a,
            f".agent/daemon/acks/{requested.control_id}.json",
            {
                "id": requested.control_id,
                "action": "cancel_task",
                "status": "accepted",
                "task_id": "different-task",
            },
            "Publish malformed workflow cancellation ACK",
        )

        with self.assertRaisesRegex(WorkflowGitIntegrityError, "task id mismatch"):
            self.cancellation.inspect(
                self.repo_a,
                str(task["id"]),
                digest,
            )


if __name__ == "__main__":
    unittest.main()
