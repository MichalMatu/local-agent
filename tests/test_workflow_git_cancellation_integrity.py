from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.runtime.task_contract import task_digest
from local_agent.workflow.git_cancellation import GitWorkflowCancellationTransport
from local_agent.workflow.git_control_plane import (
    GitWorkflowControlPlane,
    WorkflowGitIntegrityError,
)
from tests.test_workflow_git_control_plane import (
    init_remote,
    publish_from_seed,
    remote_json,
    run_git,
    workflow_task,
)


class WorkflowGitCancellationIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repository, self.origin, self.seed = init_remote(self.root, "repo-a")
        self.control = GitWorkflowControlPlane(
            origin_url_for=lambda _repository: self.origin.as_uri()
        )
        self.transport = GitWorkflowCancellationTransport(self.control)

    def test_prior_cancel_ack_with_wrong_task_id_cannot_release_control_slot(self) -> None:
        task = workflow_task("repo-a")
        digest = task_digest(task)
        self.control.publish_child(self.repository, task)

        run_git(self.seed, "pull", "--rebase", "origin", "agent-control")
        existing = {
            "id": "prior-cancel",
            "action": "cancel_task",
            "task_id": "prior-task",
        }
        publish_from_seed(
            self.seed,
            ".agent/daemon/control.json",
            existing,
            "Publish prior cancellation request",
        )
        run_git(self.seed, "pull", "--rebase", "origin", "agent-control")
        publish_from_seed(
            self.seed,
            ".agent/daemon/acks/prior-cancel.json",
            {
                "id": "prior-cancel",
                "action": "cancel_task",
                "status": "completed",
                "task_id": "different-task",
            },
            "Publish mismatched prior cancellation ACK",
        )

        with self.assertRaisesRegex(WorkflowGitIntegrityError, "ACK task id mismatch"):
            self.transport.request_cancel(
                self.repository,
                str(task["id"]),
                digest,
            )
        self.assertEqual(
            remote_json(self.origin, "agent-control", ".agent/daemon/control.json"),
            existing,
        )

    def test_malformed_prior_cancel_request_fails_closed(self) -> None:
        task = workflow_task("repo-a")
        digest = task_digest(task)
        self.control.publish_child(self.repository, task)

        run_git(self.seed, "pull", "--rebase", "origin", "agent-control")
        malformed = {
            "id": "prior-cancel",
            "action": "cancel_task",
        }
        publish_from_seed(
            self.seed,
            ".agent/daemon/control.json",
            malformed,
            "Publish malformed prior cancellation request",
        )

        with self.assertRaisesRegex(WorkflowGitIntegrityError, "invalid task id"):
            self.transport.request_cancel(
                self.repository,
                str(task["id"]),
                digest,
            )
        self.assertEqual(
            remote_json(self.origin, "agent-control", ".agent/daemon/control.json"),
            malformed,
        )


if __name__ == "__main__":
    unittest.main()
