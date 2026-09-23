from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import evidence
from local_agent.workflow.git_control_plane import (
    GitWorkflowControlPlane,
    WorkflowGitIntegrityError,
    WorkflowGitRepositoryBusyError,
)


BINDINGS = {
    "repo-a": "00000000-0000-4000-8000-000000000161",
    "repo-b": "00000000-0000-4000-8000-000000000162",
}


def run_git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=20,
    )
    if check and completed.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {completed.stdout}")
    return completed


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def init_remote(root: Path, repository_id: str) -> tuple[RepositoryContext, Path, Path]:
    repo_root = root / repository_id
    origin = repo_root / "origin.git"
    origin.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, stdout=subprocess.PIPE)

    seed = repo_root / "seed"
    seed.mkdir()
    run_git(seed, "init")
    run_git(seed, "config", "user.email", "workflow-test@example.invalid")
    run_git(seed, "config", "user.name", "Workflow Test")
    run_git(seed, "checkout", "-b", "agent-control")
    for relative in (".agent/tasks", ".agent/results", ".agent/status"):
        (seed / relative).mkdir(parents=True)
    (seed / ".agent" / ".gitkeep").write_text("test-only\n", encoding="utf-8")
    run_git(seed, "add", ".agent/.gitkeep")
    run_git(seed, "commit", "-m", "Initialize disposable control branch")
    run_git(seed, "remote", "add", "origin", origin.as_uri())
    run_git(seed, "push", "-u", "origin", "agent-control")

    control = repo_root / "control"
    subprocess.run(
        [
            "git",
            "clone",
            "--branch",
            "agent-control",
            "--single-branch",
            origin.as_uri(),
            str(control),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    run_git(control, "config", "user.email", "workflow-test@example.invalid")
    run_git(control, "config", "user.name", "Workflow Test")

    repository = RepositoryContext(
        repository_id=repository_id,
        repository=f"Owner/{repository_id}",
        control=control,
        work=repo_root / "work",
        checkpoints=repo_root / "checkpoints",
        control_branch="agent-control",
        agent_binding=BINDINGS[repository_id],
    )
    return repository, origin, seed


def workflow_task(repository_id: str, *, command: str = "true") -> dict:
    return {
        "id": "wf-" + ("a" if repository_id == "repo-a" else "b") * 64,
        "agent_binding": BINDINGS[repository_id],
        "resources": [],
        "commands": [command],
    }


def remote_json(origin: Path, branch: str, relative: str) -> dict | None:
    completed = subprocess.run(
        ["git", "--git-dir", str(origin), "show", f"{branch}:{relative}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )
    if completed.returncode != 0:
        return None
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise AssertionError("remote JSON must be an object")
    return payload


def remote_commit_count(origin: Path) -> int:
    completed = subprocess.run(
        ["git", "--git-dir", str(origin), "rev-list", "--count", "agent-control"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
        timeout=20,
    )
    return int(completed.stdout.strip())


def publish_from_seed(seed: Path, relative: str, payload: dict, message: str) -> None:
    write_json(seed / relative, payload)
    run_git(seed, "add", "--", relative)
    run_git(seed, "commit", "-m", message, "--", relative)
    run_git(seed, "push", "origin", "agent-control")


class LostPushResponseControlPlane(GitWorkflowControlPlane):
    """Simulate a push that reaches the remote but reports failure to the caller."""

    def _push_control_branch(self, repository: RepositoryContext) -> dict:
        delivered = super()._push_control_branch(repository)
        if delivered["exit_code"] != 0:
            return delivered
        return {
            "exit_code": 1,
            "output": "simulated lost push acknowledgement",
            "timed_out": True,
        }


class WorkflowGitControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo_a, self.origin_a, self.seed_a = init_remote(self.root, "repo-a")
        self.repo_b, self.origin_b, self.seed_b = init_remote(self.root, "repo-b")
        self.origins = {
            "repo-a": self.origin_a.as_uri(),
            "repo-b": self.origin_b.as_uri(),
        }
        self.control = GitWorkflowControlPlane(
            origin_url_for=lambda repository: self.origins[repository.repository_id]
        )

    def test_publish_pushes_exact_task_and_identical_retry_is_idempotent(self) -> None:
        task = workflow_task("repo-a")
        self.control.publish_child(self.repo_a, task)
        relative = f".agent/tasks/{task['id']}.json"
        observed = remote_json(self.origin_a, "agent-control", relative)
        self.assertEqual(observed, task)
        self.assertEqual(remote_commit_count(self.origin_a), 2)

        self.control.publish_child(self.repo_a, task)
        self.assertEqual(remote_commit_count(self.origin_a), 2)
        evidence_state = self.control.inspect_child(
            self.repo_a,
            str(task["id"]),
            task_digest(task),
        )
        self.assertEqual(evidence_state.kind, evidence.ChildEvidenceKind.PENDING)

    def test_two_repositories_publish_only_to_their_exact_remote(self) -> None:
        task_a = workflow_task("repo-a")
        task_b = workflow_task("repo-b")
        self.control.publish_child(self.repo_a, task_a)
        self.control.publish_child(self.repo_b, task_b)
        self.assertEqual(
            remote_json(
                self.origin_a,
                "agent-control",
                f".agent/tasks/{task_a['id']}.json",
            ),
            task_a,
        )
        self.assertIsNone(
            remote_json(
                self.origin_b,
                "agent-control",
                f".agent/tasks/{task_a['id']}.json",
            )
        )
        self.assertEqual(
            remote_json(
                self.origin_b,
                "agent-control",
                f".agent/tasks/{task_b['id']}.json",
            ),
            task_b,
        )

    def test_stale_control_checkout_is_synchronized_before_inspection(self) -> None:
        task = workflow_task("repo-a")
        publish_from_seed(
            self.seed_a,
            f".agent/tasks/{task['id']}.json",
            task,
            "Queue child from concurrent writer",
        )
        observed = self.control.inspect_child(
            self.repo_a,
            str(task["id"]),
            task_digest(task),
        )
        self.assertEqual(observed.kind, evidence.ChildEvidenceKind.PENDING)
        local = json.loads(
            (
                self.repo_a.control
                / ".agent"
                / "tasks"
                / f"{task['id']}.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(local, task)

    def test_same_id_different_digest_fails_closed(self) -> None:
        expected = workflow_task("repo-a")
        conflicting = workflow_task("repo-a", command="false")
        publish_from_seed(
            self.seed_a,
            f".agent/tasks/{expected['id']}.json",
            conflicting,
            "Queue conflicting child",
        )
        with self.assertRaisesRegex(WorkflowGitIntegrityError, "conflicting evidence"):
            self.control.publish_child(self.repo_a, expected)
        self.assertEqual(remote_commit_count(self.origin_a), 2)

    def test_unrelated_remote_task_blocks_publication_after_sync(self) -> None:
        child = workflow_task("repo-a")
        unrelated = {
            "id": "standalone-task",
            "agent_binding": BINDINGS["repo-a"],
            "resources": [],
            "commands": ["true"],
        }
        publish_from_seed(
            self.seed_a,
            ".agent/tasks/standalone-task.json",
            unrelated,
            "Queue unrelated task",
        )
        self.assertTrue(self.control.has_unrelated_work(self.repo_a, str(child["id"])))
        with self.assertRaises(WorkflowGitRepositoryBusyError):
            self.control.publish_child(self.repo_a, child)
        self.assertIsNone(
            remote_json(
                self.origin_a,
                "agent-control",
                f".agent/tasks/{child['id']}.json",
            )
        )

    def test_lost_push_response_is_proven_from_remote_without_duplicate_commit(self) -> None:
        task = workflow_task("repo-a")
        lost_ack = LostPushResponseControlPlane(
            origin_url_for=lambda repository: self.origins[repository.repository_id]
        )
        lost_ack.publish_child(self.repo_a, task)
        self.assertEqual(remote_commit_count(self.origin_a), 2)
        self.assertEqual(
            remote_json(
                self.origin_a,
                "agent-control",
                f".agent/tasks/{task['id']}.json",
            ),
            task,
        )
        status = run_git(self.repo_a.control, "status", "--porcelain").stdout.strip()
        self.assertEqual(status, "")

        lost_ack.publish_child(self.repo_a, task)
        self.assertEqual(remote_commit_count(self.origin_a), 2)

    def test_origin_mismatch_is_rejected_before_read_or_write(self) -> None:
        task = workflow_task("repo-a")
        wrong = GitWorkflowControlPlane(
            origin_url_for=lambda _repository: self.origin_b.as_uri()
        )
        with self.assertRaisesRegex(WorkflowGitIntegrityError, "origin mismatch"):
            wrong.inspect_child(
                self.repo_a,
                str(task["id"]),
                task_digest(task),
            )
        self.assertEqual(remote_commit_count(self.origin_a), 1)

    def test_local_unpushed_control_commit_is_rejected_as_non_exact_remote_state(self) -> None:
        marker = self.repo_a.control / ".agent" / "local-only.txt"
        marker.write_text("local only\n", encoding="utf-8")
        run_git(self.repo_a.control, "add", ".agent/local-only.txt")
        run_git(self.repo_a.control, "commit", "-m", "Local only control mutation")
        task = workflow_task("repo-a")
        with self.assertRaisesRegex(WorkflowGitIntegrityError, "not exact remote state"):
            self.control.inspect_child(
                self.repo_a,
                str(task["id"]),
                task_digest(task),
            )
        self.assertEqual(remote_commit_count(self.origin_a), 1)


if __name__ == "__main__":
    unittest.main()
