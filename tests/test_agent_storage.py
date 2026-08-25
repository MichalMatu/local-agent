from __future__ import annotations

import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import agent_storage as storage


class StoragePolicyTests(unittest.TestCase):
    def test_bounded_pull_keeps_control_history_at_256(self) -> None:
        self.assertEqual(storage.CONTROL_HISTORY_DEPTH, 256)
        self.assertEqual(
            storage.bounded_control_pull_args("agent-control"),
            [
                "pull",
                "--rebase",
                "--depth",
                "256",
                "--no-tags",
                "origin",
                "agent-control",
            ],
        )

    def test_sync_control_checks_out_then_uses_bounded_pull(self) -> None:
        process = mock.Mock(
            side_effect=[
                {"exit_code": 0, "output": ""},
                {"exit_code": 0, "output": ""},
            ]
        )
        core = SimpleNamespace(
            CONTROL=Path("/tmp/control"),
            CONTROL_BRANCH="agent-control",
            CONTROL_GIT_LOCK=nullcontext(),
            process=process,
        )

        storage.sync_control(core)

        self.assertEqual(process.call_count, 2)
        self.assertEqual(
            process.call_args_list[0].args,
            (["git", "checkout", "agent-control"], Path("/tmp/control")),
        )
        self.assertEqual(
            process.call_args_list[1].args,
            (
                [
                    "git",
                    "pull",
                    "--rebase",
                    "--depth",
                    "256",
                    "--no-tags",
                    "origin",
                    "agent-control",
                ],
                Path("/tmp/control"),
            ),
        )

    def test_transient_ssh_failure_is_retried_and_recovers(self) -> None:
        process = mock.Mock(
            side_effect=[
                {
                    "exit_code": 1,
                    "output": (
                        "Connection closed by 140.82.121.36 port 443\n"
                        "fatal: Could not read from remote repository."
                    ),
                },
                {"exit_code": 0, "output": "Already up to date."},
            ]
        )
        core = SimpleNamespace(process=process, log=mock.Mock())

        with mock.patch.object(storage.time, "sleep") as sleep:
            result = storage.run_git_with_network_retry(
                core,
                ["git", "pull", "origin", "agent-control"],
                Path("/tmp/control"),
            )

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(process.call_count, 2)
        sleep.assert_called_once_with(2.0)
        self.assertIn("retrying in 2s", core.log.call_args.args[0])

    def test_deterministic_git_failure_is_not_retried(self) -> None:
        process = mock.Mock(
            return_value={
                "exit_code": 1,
                "output": "git@github.com: Permission denied (publickey).",
            }
        )
        core = SimpleNamespace(process=process, log=mock.Mock())

        with mock.patch.object(storage.time, "sleep") as sleep:
            result = storage.run_git_with_network_retry(
                core,
                ["git", "pull", "origin", "agent-control"],
                Path("/tmp/control"),
            )

        self.assertEqual(result["exit_code"], 1)
        process.assert_called_once()
        sleep.assert_not_called()
        core.log.assert_not_called()

    def test_timeout_is_treated_as_transient_transport_failure(self) -> None:
        process = mock.Mock(
            side_effect=[
                {"exit_code": 124, "output": "", "timed_out": True},
                {"exit_code": 0, "output": ""},
            ]
        )
        core = SimpleNamespace(process=process, log=mock.Mock())

        with mock.patch.object(storage.time, "sleep") as sleep:
            result = storage.run_git_with_network_retry(
                core,
                ["git", "fetch", "origin", "main"],
                Path("/tmp/repo"),
            )

        self.assertEqual(result["exit_code"], 0)
        sleep.assert_called_once_with(2.0)


if __name__ == "__main__":
    unittest.main()
