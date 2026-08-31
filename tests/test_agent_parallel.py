from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

import agent_parallel as parallel
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

    def test_recently_active_repository_uses_hot_polling(self) -> None:
        schedule = parallel.RepositorySchedule(
            last_poll_at=100.0,
            last_activity_at=100.0,
        )
        self.assertFalse(parallel.repository_due(schedule, now=101.9))
        self.assertTrue(parallel.repository_due(schedule, now=102.0))


if __name__ == "__main__":
    unittest.main()
