from __future__ import annotations

import json
import tempfile
import threading
from contextlib import nullcontext
import unittest
from pathlib import Path
from unittest import mock

import local_agent.daemon.service as agentd


class AgentDaemonSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.originals = {
            "STATE_DIR": agentd.STATE_DIR,
            "CLAIMS_DIR": agentd.CLAIMS_DIR,
            "CORRUPT_CLAIMS_DIR": agentd.CORRUPT_CLAIMS_DIR,
            "DAEMON_LOCK_PATH": agentd.DAEMON_LOCK_PATH,
            "REJECTED_UPDATE_PATH": agentd.REJECTED_UPDATE_PATH,
            "LOCAL_STATUS_PATH": agentd.LOCAL_STATUS_PATH,
            "LOCAL_RUNS_DIR": agentd.LOCAL_RUNS_DIR,
            "RESULT_SPOOL_DIR": agentd.RESULT_SPOOL_DIR,
            "CONTROL": agentd.core.CONTROL,
        }
        agentd.STATE_DIR = root / "state"
        agentd.CLAIMS_DIR = agentd.STATE_DIR / "claims"
        agentd.CORRUPT_CLAIMS_DIR = agentd.STATE_DIR / "corrupt-claims"
        agentd.DAEMON_LOCK_PATH = agentd.STATE_DIR / "agentd.lock"
        agentd.REJECTED_UPDATE_PATH = agentd.STATE_DIR / "rejected-self-update.json"
        agentd.LOCAL_STATUS_PATH = agentd.STATE_DIR / "status.json"
        agentd.LOCAL_RUNS_DIR = agentd.STATE_DIR / "runs"
        agentd.RESULT_SPOOL_DIR = agentd.STATE_DIR / "result-spool"
        agentd.core.CONTROL = root / "control"
        (agentd.core.CONTROL / ".git").mkdir(parents=True)
        (agentd.core.CONTROL / ".agent" / "tasks").mkdir(parents=True)
        (agentd.core.CONTROL / ".agent" / "results").mkdir(parents=True)

    def tearDown(self) -> None:
        for key, value in self.originals.items():
            if key == "CONTROL":
                agentd.core.CONTROL = value
            else:
                setattr(agentd, key, value)
        self.tmp.cleanup()

    def task(self, task_id: str = "task-1") -> dict:
        return {"id": task_id, "mode": "commands", "resources": [], "commands": ["true"]}

    def test_publish_control_json_keeps_successful_git_plumbing_quiet(self) -> None:
        process = mock.Mock(side_effect=[
            {"exit_code": 0, "output": ""},
            {"exit_code": 1, "output": ""},
            {"exit_code": 0, "output": ""},
        ])
        retry = mock.Mock(side_effect=[
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": ""},
        ])
        with mock.patch.object(agentd.core, "process", process), mock.patch.object(
            agentd.storage,
            "run_git_with_network_retry",
            retry,
        ), mock.patch.object(
            agentd,
            "termination_critical_section",
            return_value=nullcontext(),
        ):
            published = agentd.publish_control_json(
                ".agent/status/daemon.json",
                {"state": "idle"},
                commit_message="Agent daemon status: idle",
            )
        self.assertTrue(published)
        self.assertTrue(process.call_args_list)
        self.assertTrue(
            all(call.kwargs.get("log_commands") is False for call in process.call_args_list)
        )
        self.assertEqual(retry.call_count, 2)
        self.assertTrue(
            all(call.kwargs.get("log_commands") is False for call in retry.call_args_list)
        )

    def test_quiet_control_git_failure_keeps_diagnostic(self) -> None:
        failure = {
            "exit_code": 124,
            "output": "",
            "timed_out": True,
            "elapsed_seconds": 30.0,
        }
        with mock.patch.object(agentd.core, "process", return_value=failure), mock.patch.object(
            agentd,
            "termination_critical_section",
            return_value=nullcontext(),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed_out=true"):
                agentd.publish_control_json(
                    ".agent/status/daemon.json",
                    {"state": "idle"},
                    commit_message="Agent daemon status: idle",
                )

    def test_daemon_status_reports_hardened_watchdog_defaults(self) -> None:
        with mock.patch.object(agentd, "self_revision", return_value="abc"):
            payload = agentd.daemon_status_payload("idle")
        self.assertEqual(payload["daemon_version"], agentd.DAEMON_VERSION)
        self.assertEqual(payload["command_timeout_default"], agentd.TIMEOUTS.command_default)
        self.assertEqual(payload["command_timeout_max"], agentd.TIMEOUTS.command_max)
        self.assertEqual(payload["idle_timeout_default"], agentd.TIMEOUTS.idle_default)
        self.assertEqual(payload["idle_timeout_max"], agentd.TIMEOUTS.idle_max)
        self.assertEqual(payload["task_timeout_default"], agentd.TIMEOUTS.task_default)
        self.assertEqual(payload["task_timeout_max"], agentd.TIMEOUTS.task_max)
        self.assertEqual(payload["memory_limit_mb_default"], 4096)

    def test_daemon_status_can_be_persisted_without_remote_git(self) -> None:
        with mock.patch.object(agentd, "self_revision", return_value="abc"), mock.patch.object(agentd, "publish_control_json") as publish:
            agentd.publish_daemon_status("running", force_remote=True, remote_enabled=False)
        publish.assert_not_called()
        payload = json.loads(agentd.LOCAL_STATUS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "running")

    def test_claim_blocks_duplicate_execution_and_records_digest(self) -> None:
        task = self.task()
        claim = agentd.claim_task(task)
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim["task_digest"], agentd.task_digest(task))
        self.assertIsNone(agentd.claim_task(task))
        agentd.release_task_claim("task-1")
        self.assertIsNotNone(agentd.claim_task(task))

    def test_claim_refuses_same_id_with_changed_payload(self) -> None:
        first = self.task()
        second = self.task()
        second["commands"] = ["false"]
        self.assertIsNotNone(agentd.claim_task(first))
        self.assertIsNone(agentd.claim_task(second))

    def test_pending_queue_skips_claimed_task(self) -> None:
        task = self.task("task-2")
        path = agentd.core.CONTROL / ".agent" / "tasks" / "task-2.json"
        path.write_text(json.dumps(task), encoding="utf-8")
        self.assertEqual(len(agentd.pending_tasks()), 1)
        self.assertIsNotNone(agentd.claim_task(task))
        self.assertEqual(agentd.pending_tasks(), [])

    def test_oversized_task_file_is_terminally_rejected_before_json_load(self) -> None:
        path = agentd.core.CONTROL / ".agent" / "tasks" / "large-task.json"
        path.write_bytes(b"{" + b" " * agentd.MAX_TASK_FILE_BYTES + b"}")
        self.assertEqual(agentd.pending_tasks(), [])

    def test_task_symlink_is_terminally_rejected(self) -> None:
        outside = Path(self.tmp.name) / "outside-task.json"
        outside.write_text(json.dumps(self.task("linked-task")), encoding="utf-8")
        link = agentd.core.CONTROL / ".agent" / "tasks" / "linked-task.json"
        link.symlink_to(outside)
        self.assertEqual(agentd.pending_tasks(), [])

    def test_claim_state_survives_result_publication_failure_and_retry_does_not_replay(self) -> None:
        task = self.task("publish-retry")
        task_path = agentd.core.CONTROL / ".agent" / "tasks" / "publish-retry.json"
        task_path.write_text(json.dumps(task), encoding="utf-8")
        with mock.patch.object(agentd, "publish_result", side_effect=RuntimeError("network down")):
            self.assertEqual(agentd.run_pending_task_once(), 1)
        claim_path = agentd.CLAIMS_DIR / "publish-retry.json"
        self.assertTrue(claim_path.exists())

        with mock.patch.object(agentd, "process_task") as execute, mock.patch.object(
            agentd,
            "publish_result",
        ):
            self.assertEqual(agentd.run_pending_task_once(), 1)
        execute.assert_not_called()

    def test_invalid_task_json_is_terminally_rejected(self) -> None:
        path = agentd.core.CONTROL / ".agent" / "tasks" / "broken-task.json"
        path.write_text("{broken", encoding="utf-8")
        self.assertEqual(agentd.pending_tasks(), [])

    def test_result_local_status_stays_durable_when_remote_status_publish_fails(self) -> None:
        task = self.task("local-status-only")
        task_path = agentd.core.CONTROL / ".agent" / "tasks" / "local-status-only.json"
        task_path.write_text(json.dumps(task), encoding="utf-8")
        with mock.patch.object(agentd, "publish_daemon_status", side_effect=RuntimeError("offline")):
            claim = agentd.claim_task(task)
            self.assertIsNotNone(claim)
            agentd.persist_local_status("running", task=task, claim=claim)
        payload = json.loads(agentd.LOCAL_STATUS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "running")
        self.assertEqual(payload["task_id"], "local-status-only")

    def test_control_lock_is_reentrant_for_nested_status_publish(self) -> None:
        with agentd.core.CONTROL_GIT_LOCK:
            with agentd.core.CONTROL_GIT_LOCK:
                self.assertTrue(True)

    def test_control_lock_serializes_threads(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def worker() -> None:
            with agentd.core.CONTROL_GIT_LOCK:
                entered.set()
                release.wait(timeout=1.0)

        with agentd.core.CONTROL_GIT_LOCK:
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertFalse(entered.wait(timeout=0.05))
        self.assertTrue(entered.wait(timeout=0.5))
        release.set()
        thread.join(timeout=1.0)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
