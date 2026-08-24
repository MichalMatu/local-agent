from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

import agent_multirepo as multi
import agent_repo_worker as worker


class QuietMultiRepositoryLoggingTests(unittest.TestCase):
    def test_supervisor_control_sync_suppresses_routine_git_output(self) -> None:
        stream = io.StringIO()
        with mock.patch.object(
            multi.agentd.core,
            "sync_control",
            side_effect=lambda: print("exec: git checkout agent-control"),
        ), contextlib.redirect_stdout(stream):
            multi.sync_control_quietly()
        self.assertEqual(stream.getvalue(), "")

    def test_worker_control_sync_suppresses_routine_git_output(self) -> None:
        stream = io.StringIO()
        with mock.patch.object(
            worker.core,
            "sync_control",
            side_effect=lambda: print("exec: git pull --rebase origin agent-control"),
        ), contextlib.redirect_stdout(stream):
            worker.sync_control_quietly()
        self.assertEqual(stream.getvalue(), "")

    def test_idle_summary_is_one_compact_line(self) -> None:
        self.assertEqual(multi.format_idle_summary(3), "no pending task (3 repositories)")
        self.assertEqual(multi.format_idle_summary(1), "no pending task (1 repository)")


if __name__ == "__main__":
    unittest.main()
