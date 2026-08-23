from __future__ import annotations

import io
import shlex
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
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


    def test_large_unified_diff_is_collapsed_only_in_live_log(self) -> None:
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 10
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        script = "\n".join(
            [
                "print('before-diff')",
                "print('diff --git a/a.txt b/a.txt')",
                "print('index 1111111..2222222 100644')",
                "print('--- a/a.txt')",
                "print('+++ b/a.txt')",
                "print('@@ -0,0 +1,120 @@')",
                "[print(f'+line-{i:03d}') for i in range(120)]",
                "print()",
                "print('after-diff')",
            ]
        )
        command = f"{shlex.quote(sys.executable)} -c " + shlex.quote(script)
        live = io.StringIO()
        with redirect_stdout(live):
            result = self.runtime.run_command(command, 5)

        rendered = live.getvalue()
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("+line-119", result["output"])
        self.assertIn("[CMD] before-diff", rendered)
        self.assertIn("large unified diff collapsed in live log", rendered)
        self.assertIn("collapsed unified diff: 1 file(s)", rendered)
        self.assertNotIn("+line-119", rendered)
        self.assertIn("[CMD] after-diff", rendered)

    def test_small_unified_diff_remains_visible_in_live_log(self) -> None:
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 10
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        script = "\n".join(
            [
                "print('diff --git a/a.txt b/a.txt')",
                "print('--- a/a.txt')",
                "print('+++ b/a.txt')",
                "print('@@ -1 +1 @@')",
                "print('-old')",
                "print('+new')",
                "print()",
                "print('done')",
            ]
        )
        command = f"{shlex.quote(sys.executable)} -c " + shlex.quote(script)
        live = io.StringIO()
        with redirect_stdout(live):
            result = self.runtime.run_command(command, 5)

        rendered = live.getvalue()
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("[CMD] +new", rendered)
        self.assertNotIn("collapsed unified diff", rendered)
        self.assertIn("[CMD] done", rendered)


if __name__ == "__main__":
    unittest.main()
