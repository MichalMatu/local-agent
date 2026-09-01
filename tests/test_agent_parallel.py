from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agent_parallel as parallel
import agent_repo_worker as serial_worker
from agent_process import ExecutionLeaseBusy
from agent_repository import RepositoryContext


def repository(repository_id: str) -> RepositoryContext:
    root = Path("/tmp") / repository_id
    return RepositoryContext(
        repository_id=repository_id,
        repository=f"owner/{repository_id}",
        control=root / "control",
        work=root / "work",
        checkpoints=root / "checkpoints",
    )


class ParallelSupervisorTests(unittest.TestCase):
    def test_default_concurrency_is_one(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(parallel.resolve_max_workers(None), 1)

    def test_cli_concurrency_overrides_environment(self) -> None:
        with mock.patch.dict(
            os.environ,
            {parallel.MAX_WORKERS_ENV: "2"},
            clear=False,
        ):
            self.assertEqual(parallel.resolve_max_workers(3), 3)

    def test_invalid_concurrency_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parallel.resolve_max_workers(0)
        with self.assertRaises(ValueError):
            parallel.resolve_max_workers(parallel.MAX_MAX_WORKERS + 1)
        with mock.patch.dict(
            os.environ,
            {parallel.MAX_WORKERS_ENV: "not-a-number"},
            clear=False,
        ):
            with self.assertRaises(ValueError):
                parallel.resolve_max_workers(None)

    def test_parallel_concurrency_is_capped_at_three(self) -> None:
        self.assertEqual(parallel.MAX_MAX_WORKERS, 3)

    def test_operator_idle_summary_is_human_readable(self) -> None:
        self.assertEqual(
            parallel.format_operator_idle_summary(3, 2),
            "IDLE no active task (3 repositories); max_workers=2",
        )

    def test_operator_idle_heartbeat_is_periodic(self) -> None:
        self.assertTrue(parallel.operator_idle_log_due(None, now=100.0))
        self.assertFalse(parallel.operator_idle_log_due(100.0, now=399.9))
        self.assertTrue(parallel.operator_idle_log_due(100.0, now=400.0))

    def test_worker_command_uses_parallel_worker(self) -> None:
        command = parallel.worker_command(repository("a"), registry_path=None)
        self.assertIn("agent_parallel_worker.py", command[1])
        self.assertEqual(command[2:4], ["--repository-id", "a"])
        self.assertIn("--expected-config-digest", command)

    def test_new_repository_is_due_immediately(self) -> None:
        self.assertTrue(
            parallel.repository_due(
                parallel.RepositorySchedule(),
                now=100.0,
            )
        )

    def test_retry_deadline_blocks_poll_until_due(self) -> None:
        schedule = parallel.RepositorySchedule(retry_not_before=101.0)
        self.assertFalse(parallel.repository_due(schedule, now=100.9))
        self.assertTrue(parallel.repository_due(schedule, now=101.0))

    def test_recently_active_repository_uses_hot_polling(self) -> None:
        schedule = parallel.RepositorySchedule(
            last_poll_at=100.0,
            last_activity_at=100.0,
        )
        self.assertFalse(parallel.repository_due(schedule, now=101.9))
        self.assertTrue(parallel.repository_due(schedule, now=102.0))

    def test_retry_helpers_and_reset(self) -> None:
        self.assertEqual([parallel.worker_failure_retry_seconds(i) for i in range(1,10)], [2.0,4.0,8.0,16.0,32.0,64.0,128.0,256.0,300.0])
        self.assertEqual([parallel.control_defer_retry_seconds(i) for i in range(1,6)], [2.0,4.0,8.0,15.0,15.0])
        self.assertTrue(parallel.repeated_failure_log_due(None,100.0))
        self.assertFalse(parallel.repeated_failure_log_due(100.0,159.9))
        self.assertTrue(parallel.repeated_failure_log_due(100.0,160.0))
        s=parallel.RepositorySchedule(consecutive_failures=4,last_failure_code=7,last_failure_log_at=100.0)
        parallel.reset_worker_failure_state(s)
        self.assertEqual((s.consecutive_failures,s.last_failure_code,s.last_failure_log_at),(0,None,None))

    def test_global_control_requires_every_repository_lease(self) -> None:
        repositories = [repository("control-a"), repository("control-b")]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            parallel.agentd,
            "STATE_DIR",
            Path(tmp),
        ):
            with serial_worker.repository_execution_lease(repositories[1]):
                with self.assertRaises(ExecutionLeaseBusy):
                    with parallel.supervisor_control_leases(repositories):
                        self.fail("global control acquired a busy repository")


if __name__ == "__main__":
    unittest.main()
