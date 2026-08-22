from __future__ import annotations

import shlex
import sys
import tempfile
import time
import unittest
from pathlib import Path

import agent_core as core
from agent_runtime import RuntimeExecutor, idle_timeout_for, task_digest, task_timeout_for, validate_task


class RuntimeExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.original_work = core.WORK
        core.WORK = Path(self.tmp.name)
        self.runtime = RuntimeExecutor(core)

    def tearDown(self) -> None:
        core.WORK = self.original_work
        self.tmp.cleanup()

    def test_task_digest_is_stable_and_payload_sensitive(self) -> None:
        a = {"id": "task-1", "commands": ["true"], "mode": "commands"}
        b = {"mode": "commands", "commands": ["true"], "id": "task-1"}
        c = {"id": "task-1", "commands": ["false"], "mode": "commands"}
        self.assertEqual(task_digest(a), task_digest(b))
        self.assertNotEqual(task_digest(a), task_digest(c))

    def test_task_validation_rejects_unsafe_id(self) -> None:
        with self.assertRaises(ValueError):
            validate_task({"id": "../bad", "commands": ["true"]})

    def test_watchdog_defaults_and_bounds(self) -> None:
        self.assertEqual(idle_timeout_for({}), 600)
        self.assertEqual(task_timeout_for({}), 3600)
        self.assertEqual(idle_timeout_for({"idle_timeout": 0}), 0)
        with self.assertRaises(ValueError):
            task_timeout_for({"task_timeout": 14401})

    def test_idle_timeout_kills_silent_command(self) -> None:
        self.runtime._idle_timeout = 1
        self.runtime._deadline = time.monotonic() + 10
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        command = f"{shlex.quote(sys.executable)} -c " + shlex.quote(
            "import time; time.sleep(5)"
        )
        result = self.runtime.run_command(command, 10)
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue(result["idle_timed_out"])

    def test_task_deadline_kills_command(self) -> None:
        self.runtime._idle_timeout = 0
        self.runtime._deadline = time.monotonic() + 1
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        command = f"{shlex.quote(sys.executable)} -c " + shlex.quote(
            "import time; time.sleep(5)"
        )
        result = self.runtime.run_command(command, 10)
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue(result["task_timed_out"])

    def test_progress_emits_command_transitions(self) -> None:
        events: list[dict] = []
        self.runtime._progress = events.append
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 10
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        result = self.runtime.run_command("printf 'ok\\n'", 5)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(events[0]["event"], "command_started")
        self.assertEqual(events[-1]["event"], "command_finished")


if __name__ == "__main__":
    unittest.main()
