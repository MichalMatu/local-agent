from __future__ import annotations

import io
import json
import shlex
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import agent_core as core
import agent_runtime as runtime_module
from agent_runtime import (
    RuntimeExecutor,
    collect_host_telemetry,
    idle_timeout_for,
    parse_mac_swapusage,
    parse_mac_ps_cpu,
    parse_mac_top_cpu,
    parse_mac_vm_stat,
    parse_process_group_ps,
    parse_progress_marker,
    task_digest,
    task_timeout_for,
    validate_task,
)


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

    def test_structured_steps_validate_and_reject_ambiguous_payloads(self) -> None:
        task = {
            "id": "staged-1",
            "steps": [{"name": "build", "command": "true", "timeout": 120}],
            "verify_steps": [{"name": "inspect", "command": "true", "timeout": 90}],
            "command_timeout": 300,
            "task_timeout": 600,
        }
        validate_task(task)
        with self.assertRaisesRegex(ValueError, "steps and commands"):
            validate_task({**task, "commands": ["true"]})
        with self.assertRaisesRegex(ValueError, "verify_steps and verify_commands"):
            validate_task({**task, "verify_commands": ["true"]})
        with self.assertRaises(ValueError):
            validate_task({"id": "bad-stage", "steps": [{"name": "", "command": "true"}]})
        with self.assertRaisesRegex(ValueError, "item timeout"):
            validate_task(
                {
                    "id": "bad-stage-timeout",
                    "steps": [{"name": "build", "command": "true", "timeout": core.MAX_COMMAND_TIMEOUT + 1}],
                }
            )

    def test_legacy_and_structured_stage_plans_have_ordered_metadata(self) -> None:
        legacy = core.stage_plan_for(
            {"commands": ["one", "two"], "verify_commands": ["check"]}
        )
        self.assertEqual(
            [(item["stage_name"], item["stage_index"], item["stage_phase"]) for item in legacy],
            [("command-1", 1, "commands"), ("command-2", 2, "commands"), ("verification-1", 3, "verification")],
        )
        self.runtime._progress = (events := []).append
        self.runtime._stage_plan = core.stage_plan_for(
            {"steps": [{"name": "compile", "command": "printf ok", "timeout": 5}]}
        )
        self.assertEqual(self.runtime._stage_plan[0]["stage_timeout"], 5)
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 120
        self.runtime.run_command("printf ok", 5)
        for event_name in ("command_started", "command_finished"):
            event = next(item for item in events if item["event"] == event_name)
            self.assertEqual(event["stage_name"], "compile")
            self.assertEqual(event["stage_index"], 1)
            self.assertEqual(event["stage_total"], 1)
            self.assertEqual(event["stage_phase"], "commands")

    def test_staged_result_contains_summary_and_stops_after_failure(self) -> None:
        task = {
            "id": "staged-result",
            "steps": [
                {"name": "first", "command": "one"},
                {"name": "second", "command": "two"},
            ],
        }
        calls: list[str] = []

        def fake_run(command: str, _timeout: int, *, stage=None):
            calls.append(command)
            return {"command": command, "exit_code": 1 if command == "one" else 0, "elapsed_seconds": 0.25}

        with mock.patch.object(core, "prepare_work"), mock.patch.object(
            core, "cleanup_work"
        ), mock.patch.object(
            core, "git_snapshot", return_value=({"exit_code": 0, "output": ""}, {"exit_code": 0, "output": ""})
        ), mock.patch.object(core, "checkpoint_worktree", return_value=None), mock.patch.object(
            core, "run_command", side_effect=fake_run
        ):
            result = core.process_task(task)

        self.assertEqual(calls, ["one"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failure_reason"], "command_failed")
        self.assertEqual(result["stages"][0]["stage_name"], "first")
        self.assertEqual(result["stages"][0]["outcome"], "failed")
        self.assertEqual(result["stages"][0]["elapsed_seconds"], 0.25)

    def test_progress_marker_parsing_and_malformed_tolerance(self) -> None:
        marker = parse_progress_marker(
            '[AGENT_PROGRESS] ' + json.dumps(
                {"stage_name": "case-run", "message": "case 2", "current": 2, "total": 5, "metrics": {"passed": 1}}
            )
        )
        self.assertEqual(marker["stage_name"], "case-run")
        self.assertEqual(marker["metrics"], {"passed": 1})
        self.assertIsNone(parse_progress_marker("[AGENT_PROGRESS] {broken"))
        self.assertIsNone(parse_progress_marker("[AGENT_PROGRESS] " + "x" * 5000))

        events: list[dict] = []
        self.runtime._progress = events.append
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 120
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        command = f"{shlex.quote(sys.executable)} -c " + shlex.quote(
            "print('[AGENT_PROGRESS] {broken}'); print('[AGENT_PROGRESS] {\\\"stage_name\\\":\\\"case-run\\\",\\\"message\\\":\\\"case 2\\\",\\\"current\\\":2,\\\"total\\\":5}')"
        )
        result = self.runtime.run_command(command, 5)
        self.assertEqual(result["exit_code"], 0)
        progress_events = [event for event in events if event["event"] == "stage_progress"]
        self.assertEqual(len(progress_events), 1)
        self.assertEqual(progress_events[0]["last_progress_message"], "case 2")
        self.assertEqual(progress_events[0]["total"], 1)
        self.assertEqual(progress_events[0]["progress_current"], 2)
        self.assertEqual(progress_events[0]["progress_total"], 5)
        self.assertEqual(progress_events[0]["stage_progress"]["total"], 5)

    def test_domain_progress_resets_between_commands(self) -> None:
        events: list[dict] = []
        self.runtime._progress = events.append
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 120
        self.runtime._command_count = 2
        self.runtime._primary_count = 2
        first = f"{shlex.quote(sys.executable)} -c " + shlex.quote(
            "print('[AGENT_PROGRESS] {\"stage_name\":\"stage-a\",\"message\":\"A\",\"current\":1,\"total\":2}')"
        )
        second = f"{shlex.quote(sys.executable)} -c " + shlex.quote(
            "import time; time.sleep(0.4)"
        )
        with mock.patch.object(runtime_module, "PROGRESS_INTERVAL", 0):
            self.assertEqual(
                self.runtime.run_command(
                    first,
                    5,
                    stage={
                        "stage_name": "stage-a",
                        "stage_index": 1,
                        "stage_total": 2,
                        "stage_phase": "commands",
                    },
                )["exit_code"],
                0,
            )
            self.assertEqual(
                self.runtime.run_command(
                    second,
                    5,
                    stage={
                        "stage_name": "stage-b",
                        "stage_index": 2,
                        "stage_total": 2,
                        "stage_phase": "commands",
                    },
                )["exit_code"],
                0,
            )

        second_heartbeats = [
            event
            for event in events
            if event["event"] == "command_heartbeat" and event["index"] == 2
        ]
        self.assertTrue(second_heartbeats)
        self.assertTrue(all("stage_progress" not in event for event in second_heartbeats))
        self.assertTrue(all("last_progress_at" not in event for event in second_heartbeats))

    def test_telemetry_parsers_are_deterministic(self) -> None:
        vm = parse_mac_vm_stat(
            "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
            "Pages free: 10\nPages inactive: 20\nPages speculative: 5\n"
        )
        self.assertEqual(vm["available_bytes"], 35 * 16384)
        fallback_vm = parse_mac_vm_stat(
            "Pages free: 10\nPages inactive: 20\nPages speculative: 5\n"
        )
        self.assertEqual(fallback_vm["available_bytes"], 35 * 4096)
        self.assertEqual(parse_mac_swapusage("total = 4.00G  used = 1.25G  free = 2.75G"), {"total": 4 * 1024**3, "used": int(1.25 * 1024**3), "free": int(2.75 * 1024**3)})
        self.assertEqual(
            parse_mac_top_cpu("CPU usage: 12.50% user, 3.25% sys, 84.25% idle"),
            15.75,
        )
        self.assertEqual(parse_mac_ps_cpu("50\n75\nnot-a-number\n", 2), 62.5)
        self.assertEqual(parse_mac_ps_cpu("500\n", 2), 100.0)
        self.assertEqual(
            parse_process_group_ps("1 99 2.0 1000\n2 99 3.5 3000\n3 12 9.0 9000", 99),
            {"command_cpu_percent": 5.5, "command_rss_mb": round(4000 / 1024, 2), "command_children": 1},
        )

    def test_heartbeat_includes_telemetry_and_survives_unavailable_metrics(self) -> None:
        events: list[dict] = []
        self.runtime._progress = events.append
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 120
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        with mock.patch.object(runtime_module, "PROGRESS_INTERVAL", 0), mock.patch.object(
            runtime_module,
            "collect_telemetry",
            side_effect=[
                {"host_cpu_percent": 12.5, "command_rss_mb": 4.0},
                {},
            ],
        ):
            result = self.runtime.run_command("printf ok", 5)
        self.assertEqual(result["exit_code"], 0)
        heartbeats = [event for event in events if event["event"] == "command_heartbeat"]
        self.assertTrue(heartbeats)
        self.assertEqual(heartbeats[0]["host_cpu_percent"], 12.5)

    def test_watchdog_defaults_and_bounds(self) -> None:
        self.assertEqual(idle_timeout_for({}), 300)
        self.assertEqual(task_timeout_for({}), 1800)
        self.assertEqual(idle_timeout_for({"idle_timeout": 0}), 0)
        with self.assertRaises(ValueError):
            task_timeout_for({"task_timeout": 1801})
        with self.assertRaises(ValueError):
            idle_timeout_for({"idle_timeout": 901})

    def test_idle_timeout_kills_silent_command(self) -> None:
        self.runtime._idle_timeout = 1
        self.runtime._deadline = time.monotonic() + 120
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        command = f"{shlex.quote(sys.executable)} -c " + shlex.quote(
            "import time; time.sleep(5)"
        )
        result = self.runtime.run_command(command, 10)
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue(result["idle_timed_out"])

    def test_task_budget_refuses_stage_before_start(self) -> None:
        self.runtime._idle_timeout = 0
        self.runtime._deadline = time.monotonic() + 100
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        stage = {
            "stage_name": "too-large",
            "stage_index": 1,
            "stage_total": 1,
            "stage_phase": "commands",
        }
        with mock.patch.object(runtime_module.subprocess, "Popen") as popen:
            result = self.runtime.run_command("printf never-runs", 60, stage=stage)
        popen.assert_not_called()
        self.assertEqual(result["exit_code"], 125)
        self.assertTrue(result["not_started"])
        self.assertTrue(result["budget_exhausted"])
        self.assertFalse(result["task_timed_out"])
        self.assertEqual(self.runtime._last_failure_reason, "task_budget_exhausted")

    def test_structured_stage_timeout_overrides_task_command_timeout(self) -> None:
        task = {
            "id": "stage-timeout-override",
            "steps": [{"name": "short", "command": "one", "timeout": 7}],
            "command_timeout": 120,
            "task_timeout": 300,
        }
        calls: list[tuple[str, int]] = []

        def fake_run(command: str, timeout: int, *, stage=None):
            calls.append((command, timeout))
            return {"command": command, "exit_code": 0, "elapsed_seconds": 0.1}

        with mock.patch.object(core, "prepare_work"), mock.patch.object(
            core, "cleanup_work"
        ), mock.patch.object(
            core, "git_snapshot", return_value=({"exit_code": 0, "output": ""}, {"exit_code": 0, "output": ""})
        ), mock.patch.object(core, "checkpoint_worktree", return_value=None), mock.patch.object(
            core, "run_command", side_effect=fake_run
        ):
            result = core.process_task(task)

        self.assertEqual(result["status"], "done")
        self.assertEqual(calls, [("one", 7)])

    def test_progress_emits_command_transitions(self) -> None:
        events: list[dict] = []
        self.runtime._progress = events.append
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 120
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        result = self.runtime.run_command("printf 'ok\\n'", 5)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(events[0]["event"], "command_started")
        self.assertEqual(events[-1]["event"], "command_finished")


    def test_large_unified_diff_is_collapsed_only_in_live_log(self) -> None:
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 120
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

    def test_indented_output_after_completed_hunk_is_not_collapsed(self) -> None:
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 120
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        script = "\n".join(
            [
                "print('diff --git a/a.txt b/a.txt')",
                "print('index 1111111..2222222 100644')",
                "print('--- a/a.txt')",
                "print('+++ b/a.txt')",
                "print('@@ -0,0 +1,81 @@')",
                "[print(f'+line-{i:03d}') for i in range(81)]",
                "print('  normal command output')",
            ]
        )
        command = f"{shlex.quote(sys.executable)} -c " + shlex.quote(script)
        live = io.StringIO()
        with redirect_stdout(live):
            result = self.runtime.run_command(command, 5)

        rendered = live.getvalue()
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("[CMD]   normal command output", rendered)
        self.assertIn("collapsed unified diff: 1 file(s), 86 line(s)", rendered)
        self.assertNotIn("collapsed unified diff: 1 file(s), 87 line(s)", rendered)

    def test_identical_large_diffs_are_aggregated_in_live_log(self) -> None:
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 120
        self.runtime._command_count = 1
        self.runtime._primary_count = 1
        script = "\n".join(
            [
                "def emit_diff():",
                "    print('diff --git a/a.txt b/a.txt')",
                "    print('index 1111111..2222222 100644')",
                "    print('--- a/a.txt')",
                "    print('+++ b/a.txt')",
                "    print('@@ -0,0 +1,81 @@')",
                "    [print(f'+line-{i:03d}') for i in range(81)]",
                "emit_diff()",
                "print()",
                "emit_diff()",
                "print()",
                "emit_diff()",
                "print('after-diffs')",
            ]
        )
        command = f"{shlex.quote(sys.executable)} -c " + shlex.quote(script)
        live = io.StringIO()
        with redirect_stdout(live):
            result = self.runtime.run_command(command, 5)

        rendered = live.getvalue()
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["output"].count("diff --git a/a.txt b/a.txt"), 3)
        self.assertEqual(rendered.count("large unified diff collapsed in live log"), 1)
        self.assertEqual(rendered.count("collapsed unified diff:"), 1)
        self.assertIn("suppressed 2 repeated copies of the previous unified diff", rendered)
        self.assertIn("[CMD] after-diffs", rendered)

    def test_small_unified_diff_remains_visible_in_live_log(self) -> None:
        self.runtime._idle_timeout = 5
        self.runtime._deadline = time.monotonic() + 120
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
