from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agent_multirepo as multi
from agent_repo_worker import WORKER_IDLE, WORKER_PROCESSED
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


class MultiRepositorySupervisorTests(unittest.TestCase):
    def test_ordered_repositories_rotates_after_last_served_repository(self) -> None:
        repositories = [repository("a"), repository("b"), repository("c")]
        ordered = multi.ordered_repositories(repositories, "a")
        self.assertEqual([item.repository_id for item in ordered], ["b", "c", "a"])
        ordered = multi.ordered_repositories(repositories, "c")
        self.assertEqual([item.repository_id for item in ordered], ["a", "b", "c"])

    def test_unknown_last_repository_falls_back_to_registry_order(self) -> None:
        repositories = [repository("a"), repository("b")]
        ordered = multi.ordered_repositories(repositories, "missing")
        self.assertEqual([item.repository_id for item in ordered], ["a", "b"])

    def test_worker_command_targets_exact_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "repositories.json"
            command = multi.worker_command(repository("a"), registry_path=registry)
        self.assertIn("agent_repo_worker.py", command[1])
        self.assertEqual(command[2:4], ["--repository-id", "a"])
        self.assertEqual(command[-2:], ["--registry", str(registry)])

    def test_cycle_continues_after_repository_worker_failure(self) -> None:
        repositories = [repository("a"), repository("b"), repository("c")]
        with mock.patch.object(
            multi, "load_repository_registry", return_value=repositories
        ), mock.patch.object(
            multi,
            "run_worker",
            side_effect=[3, WORKER_PROCESSED],
        ) as run_worker:
            processed, last_repository = multi.run_cycle(
                registry_path=None,
                start_after=None,
            )
        self.assertTrue(processed)
        self.assertEqual(last_repository, "b")
        self.assertEqual(
            [call.args[0].repository_id for call in run_worker.call_args_list],
            ["a", "b"],
        )

    def test_cycle_is_round_robin_and_stops_after_one_processed_task(self) -> None:
        repositories = [repository("a"), repository("b"), repository("c")]
        with mock.patch.object(
            multi, "load_repository_registry", return_value=repositories
        ), mock.patch.object(
            multi,
            "run_worker",
            side_effect=[WORKER_IDLE, WORKER_PROCESSED],
        ) as run_worker:
            processed, last_repository = multi.run_cycle(
                registry_path=None,
                start_after="a",
            )
        self.assertTrue(processed)
        self.assertEqual(last_repository, "c")
        self.assertEqual(
            [call.args[0].repository_id for call in run_worker.call_args_list],
            ["b", "c"],
        )

    def test_supervisor_control_uses_first_repository(self) -> None:
        repositories = [repository("a"), repository("b")]
        with mock.patch.object(
            multi, "load_repository_registry", return_value=repositories
        ):
            selected = multi.supervisor_control_repository(registry_path=None)
        self.assertEqual(selected.repository_id, "a")

    def test_service_supervisor_control_syncs_and_handles_global_actions(self) -> None:
        target = repository("a")
        original_version = multi.agentd.DAEMON_VERSION
        original_control = multi.agentd.core.CONTROL
        original_branch = multi.agentd.core.CONTROL_BRANCH
        try:
            with mock.patch.object(multi.agentd.core, "sync_control") as sync, mock.patch.object(
                multi.agentd, "handle_control_request"
            ) as handle, mock.patch.object(multi.agentd, "maybe_self_update") as update:
                multi.service_supervisor_control(target)
            self.assertEqual(multi.agentd.core.CONTROL, target.control)
            self.assertEqual(multi.agentd.DAEMON_VERSION, "4.6.0")
            sync.assert_called_once_with()
            handle.assert_called_once_with()
            update.assert_called_once_with()
        finally:
            multi.agentd.DAEMON_VERSION = original_version
            multi.agentd.core.CONTROL = original_control
            multi.agentd.core.CONTROL_BRANCH = original_branch

    def test_all_idle_preserves_last_repository_cursor(self) -> None:
        repositories = [repository("a"), repository("b")]
        with mock.patch.object(
            multi, "load_repository_registry", return_value=repositories
        ), mock.patch.object(
            multi,
            "run_worker",
            side_effect=[WORKER_IDLE, WORKER_IDLE],
        ):
            processed, last_repository = multi.run_cycle(
                registry_path=None,
                start_after="a",
            )
        self.assertFalse(processed)
        self.assertEqual(last_repository, "a")


if __name__ == "__main__":
    unittest.main()
