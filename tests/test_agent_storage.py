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


if __name__ == "__main__":
    unittest.main()
