from __future__ import annotations

import unittest

from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import evidence
from local_agent.workflow.git_control_plane import (
    GitWorkflowControlPlane,
    WorkflowGitIntegrityError,
    WorkflowGitPublicationConflict,
)
from tests.test_workflow_git_control_plane import (
    WorkflowGitControlPlaneTests,
    publish_from_seed,
    remote_commit_count,
    remote_json,
    run_git,
    workflow_task,
)


class ConcurrentPushControlPlane(GitWorkflowControlPlane):
    def __init__(self, *args, before_push, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._before_push = before_push
        self._injected = False

    def _push_control_branch(self, repository):
        if not self._injected:
            self._injected = True
            self._before_push()
        return super()._push_control_branch(repository)


class WorkflowGitControlPlaneRaceTests(WorkflowGitControlPlaneTests):
    # Inherit the base adapter tests so this file can also be run independently while
    # sharing the same disposable-bare-remote fixture. Additional tests below focus on
    # recovery and checkout integrity edges.

    def test_concurrent_exact_same_child_is_recovered_as_idempotent_success(self) -> None:
        task = workflow_task("repo-a")
        relative = f".agent/tasks/{task['id']}.json"

        def publish_same_remote_child() -> None:
            publish_from_seed(
                self.seed_a,
                relative,
                task,
                "Concurrent exact workflow child",
            )

        control = ConcurrentPushControlPlane(
            origin_url_for=lambda repository: self.origins[repository.repository_id],
            before_push=publish_same_remote_child,
        )
        control.publish_child(self.repo_a, task)

        self.assertEqual(remote_commit_count(self.origin_a), 2)
        self.assertEqual(remote_json(self.origin_a, "agent-control", relative), task)
        self.assertEqual(run_git(self.repo_a.control, "status", "--porcelain").stdout.strip(), "")
        self.assertEqual(
            run_git(self.repo_a.control, "rev-parse", "HEAD").stdout.strip(),
            run_git(self.repo_a.control, "rev-parse", "refs/remotes/origin/agent-control").stdout.strip(),
        )

    def test_concurrent_unrelated_remote_commit_aborts_child_and_aligns_checkout(self) -> None:
        task = workflow_task("repo-a")
        unrelated = {
            "id": "concurrent-standalone",
            "agent_binding": task["agent_binding"],
            "resources": [],
            "commands": ["true"],
        }

        def publish_unrelated() -> None:
            publish_from_seed(
                self.seed_a,
                ".agent/tasks/concurrent-standalone.json",
                unrelated,
                "Concurrent unrelated task",
            )

        control = ConcurrentPushControlPlane(
            origin_url_for=lambda repository: self.origins[repository.repository_id],
            before_push=publish_unrelated,
        )
        with self.assertRaises(WorkflowGitPublicationConflict):
            control.publish_child(self.repo_a, task)

        self.assertIsNone(
            remote_json(
                self.origin_a,
                "agent-control",
                f".agent/tasks/{task['id']}.json",
            )
        )
        self.assertEqual(
            remote_json(
                self.origin_a,
                "agent-control",
                ".agent/tasks/concurrent-standalone.json",
            ),
            unrelated,
        )
        self.assertEqual(run_git(self.repo_a.control, "status", "--porcelain").stdout.strip(), "")
        self.assertEqual(
            run_git(self.repo_a.control, "rev-parse", "HEAD").stdout.strip(),
            run_git(self.repo_a.control, "rev-parse", "refs/remotes/origin/agent-control").stdout.strip(),
        )

    def test_clean_wrong_branch_is_corrected_before_evidence_read(self) -> None:
        run_git(self.repo_a.control, "checkout", "-b", "temporary-other-branch")
        task = workflow_task("repo-a")
        observed = self.control.inspect_child(
            self.repo_a,
            str(task["id"]),
            task_digest(task),
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.ABSENT)
        self.assertEqual(
            run_git(self.repo_a.control, "branch", "--show-current").stdout.strip(),
            "agent-control",
        )

    def test_dirty_checkout_is_rejected_before_sync(self) -> None:
        dirty = self.repo_a.control / ".agent" / "manual-local-change.txt"
        dirty.write_text("do not discard\n", encoding="utf-8")
        task = workflow_task("repo-a")
        with self.assertRaisesRegex(WorkflowGitIntegrityError, "unexpected local changes"):
            self.control.inspect_child(
                self.repo_a,
                str(task["id"]),
                task_digest(task),
            )
        self.assertEqual(dirty.read_text(encoding="utf-8"), "do not discard\n")

    def test_malformed_remote_result_fails_closed_instead_of_hiding_task(self) -> None:
        task = workflow_task("repo-a")
        self.control.publish_child(self.repo_a, task)

        run_git(self.seed_a, "pull", "--rebase", "origin", "agent-control")
        result_path = self.seed_a / ".agent" / "results" / f"{task['id']}.json"
        result_path.write_text("{not-json\n", encoding="utf-8")
        relative = result_path.relative_to(self.seed_a).as_posix()
        run_git(self.seed_a, "add", "--", relative)
        run_git(self.seed_a, "commit", "-m", "Publish malformed result", "--", relative)
        run_git(self.seed_a, "push", "origin", "agent-control")

        with self.assertRaisesRegex(WorkflowGitIntegrityError, "invalid workflow control JSON"):
            self.control.inspect_child(
                self.repo_a,
                str(task["id"]),
                task_digest(task),
            )

    def test_terminal_unrelated_task_does_not_block_after_exact_result_arrives(self) -> None:
        child = workflow_task("repo-a")
        unrelated = {
            "id": "standalone-terminal",
            "agent_binding": child["agent_binding"],
            "resources": [],
            "commands": ["true"],
        }
        publish_from_seed(
            self.seed_a,
            ".agent/tasks/standalone-terminal.json",
            unrelated,
            "Queue standalone terminal task",
        )
        self.assertTrue(self.control.has_unrelated_work(self.repo_a, str(child["id"])))

        run_git(self.seed_a, "pull", "--rebase", "origin", "agent-control")
        result = {
            "id": unrelated["id"],
            "status": "done",
            "task_digest": task_digest(unrelated),
        }
        publish_from_seed(
            self.seed_a,
            ".agent/results/standalone-terminal.json",
            result,
            "Complete standalone terminal task",
        )
        self.assertFalse(self.control.has_unrelated_work(self.repo_a, str(child["id"])))


if __name__ == "__main__":
    unittest.main()
