from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agent_core as core
import agent_repo_worker as worker
import agentd
from agent_repository import RepositoryContext


class RepositoryWorkerTests(unittest.TestCase):
    def test_worker_version_matches_agent_release(self) -> None:
        self.assertEqual(worker.MULTIREPO_DAEMON_VERSION, agentd.DAEMON_VERSION)

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repository = RepositoryContext(
            repository_id="project-a",
            repository="owner/project-a",
            control=root / "control",
            work=root / "work",
            checkpoints=root / "checkpoints",
        )
        (self.repository.control / ".git").mkdir(parents=True)
        (self.repository.work / ".git").mkdir(parents=True)
        self.originals = {
            "STATE_DIR": agentd.STATE_DIR,
            "CONTROL": core.CONTROL,
            "WORK": core.WORK,
            "CHECKPOINTS": core.CHECKPOINTS,
            "CONTROL_BRANCH": core.CONTROL_BRANCH,
            "CLAIMS_DIR": agentd.CLAIMS_DIR,
            "CORRUPT_CLAIMS_DIR": agentd.CORRUPT_CLAIMS_DIR,
            "LOCAL_STATUS_PATH": agentd.LOCAL_STATUS_PATH,
            "LOCAL_RUNS_DIR": agentd.LOCAL_RUNS_DIR,
            "RESULT_SPOOL_DIR": agentd.RESULT_SPOOL_DIR,
        }
        agentd.STATE_DIR = root / "state"

    def tearDown(self) -> None:
        core.CONTROL = self.originals["CONTROL"]
        core.WORK = self.originals["WORK"]
        core.CHECKPOINTS = self.originals["CHECKPOINTS"]
        core.CONTROL_BRANCH = self.originals["CONTROL_BRANCH"]
        agentd.CLAIMS_DIR = self.originals["CLAIMS_DIR"]
        agentd.CORRUPT_CLAIMS_DIR = self.originals["CORRUPT_CLAIMS_DIR"]
        agentd.LOCAL_STATUS_PATH = self.originals["LOCAL_STATUS_PATH"]
        agentd.LOCAL_RUNS_DIR = self.originals["LOCAL_RUNS_DIR"]
        agentd.RESULT_SPOOL_DIR = self.originals["RESULT_SPOOL_DIR"]
        agentd.STATE_DIR = self.originals["STATE_DIR"]
        self.tmp.cleanup()

    def test_bind_repository_scopes_paths_inside_worker_process(self) -> None:
        worker.bind_repository(self.repository)
        self.assertEqual(core.CONTROL, self.repository.control)
        self.assertEqual(core.WORK, self.repository.work)
        self.assertEqual(core.CHECKPOINTS, self.repository.checkpoints)
        self.assertEqual(core.CONTROL_BRANCH, "agent-control")
        state = worker.repository_state_dir(self.repository)
        self.assertEqual(agentd.CLAIMS_DIR, state / "claims")
        self.assertEqual(agentd.LOCAL_RUNS_DIR, state / "runs")
        self.assertEqual(agentd.RESULT_SPOOL_DIR, state / "result-spool")

    def test_missing_checkout_is_rejected_before_git_mutation(self) -> None:
        missing = RepositoryContext(
            repository_id="missing",
            repository="owner/missing",
            control=Path(self.tmp.name) / "missing-control",
            work=Path(self.tmp.name) / "missing-work",
            checkpoints=Path(self.tmp.name) / "missing-checkpoints",
        )
        with self.assertRaisesRegex(RuntimeError, "checkout missing"):
            worker.validate_repository_checkouts(missing)

    def test_idle_poll_executes_no_task(self) -> None:
        with mock.patch.object(core, "sync_control"), mock.patch.object(
            agentd, "recover_stale_claims"
        ), mock.patch.object(agentd, "recover_invalid_task_files"), mock.patch.object(
            agentd, "pending_tasks", return_value=[]
        ), mock.patch.object(agentd, "execute_task") as execute_task:
            processed = worker.poll_repository_once(self.repository)
        self.assertFalse(processed)
        execute_task.assert_not_called()

    def test_poll_executes_at_most_first_task(self) -> None:
        tasks = [
            (Path("one.json"), {"id": "one", "commands": ["true"]}),
            (Path("two.json"), {"id": "two", "commands": ["true"]}),
        ]
        with mock.patch.object(core, "sync_control"), mock.patch.object(
            agentd, "recover_stale_claims"
        ), mock.patch.object(agentd, "recover_invalid_task_files"), mock.patch.object(
            agentd, "pending_tasks", return_value=tasks
        ), mock.patch.object(agentd, "execute_task") as execute_task:
            processed = worker.poll_repository_once(self.repository)
        self.assertTrue(processed)
        execute_task.assert_called_once_with(tasks[0][1])

    def test_publication_pending_is_not_overwritten_with_idle(self) -> None:
        tasks = [(Path("one.json"), {"id": "one", "commands": ["true"]})]
        with mock.patch.object(core, "sync_control"), mock.patch.object(
            agentd, "recover_stale_claims"
        ), mock.patch.object(agentd, "recover_invalid_task_files"), mock.patch.object(
            agentd, "pending_tasks", return_value=tasks
        ), mock.patch.object(
            agentd, "execute_task", return_value="publication_pending"
        ), mock.patch.object(worker, "publish_repository_status") as publish_status:
            processed = worker.poll_repository_once(self.repository)
        self.assertTrue(processed)
        publish_status.assert_called_once_with(
            self.repository,
            "publication_pending",
            force_remote=True,
            last_task_id="one",
        )


if __name__ == "__main__":
    unittest.main()
