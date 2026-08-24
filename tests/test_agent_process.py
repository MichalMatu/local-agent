from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from agent_process import BoundedTextBuffer, process_group_for, terminate_process_group


class BoundedTextBufferTests(unittest.TestCase):
    def test_buffer_keeps_exact_tail_across_chunks(self) -> None:
        buffer = BoundedTextBuffer(8)
        buffer.append("abc")
        buffer.append("defgh")
        buffer.append("ij")
        self.assertEqual(buffer.text(), "cdefghij")
        self.assertEqual(len(buffer), 8)

    def test_single_large_chunk_is_strictly_bounded(self) -> None:
        buffer = BoundedTextBuffer(5)
        buffer.append("0123456789")
        self.assertEqual(buffer.text(), "56789")
        self.assertEqual(len(buffer), 5)


class ProcessGroupTests(unittest.TestCase):
    def test_stored_process_group_survives_parent_exit(self) -> None:
        proc = mock.Mock(spec=subprocess.Popen)
        proc.pid = 123
        proc.poll.return_value = 0
        setattr(proc, "_local_agent_process_group", 456)
        self.assertEqual(process_group_for(proc), 456)

    def test_terminate_escalates_when_group_remains_alive(self) -> None:
        proc = mock.Mock(spec=subprocess.Popen)
        proc.pid = 123
        setattr(proc, "_local_agent_process_group", 456)
        log = mock.Mock()
        with mock.patch("agent_process.os.getpgrp", return_value=999), mock.patch(
            "agent_process.os.killpg"
        ) as killpg, mock.patch(
            "agent_process.process_group_alive", side_effect=[True, True, True]
        ), mock.patch("agent_process.time.monotonic", side_effect=[0.0, 0.0, 1.0]), mock.patch(
            "agent_process.time.sleep"
        ):
            terminate_process_group(proc, log, grace_seconds=0.5)

        self.assertEqual(killpg.call_args_list[0].args[0], 456)
        self.assertEqual(killpg.call_args_list[-1].args[0], 456)
        self.assertEqual(killpg.call_count, 2)


if __name__ == "__main__":
    unittest.main()
