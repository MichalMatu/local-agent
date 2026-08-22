from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agentd


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
            "CONTROL": agentd.core.CONTROL,
        }
        agentd.STATE_DIR = root / "state"
        agentd.CLAIMS_DIR = agentd.STATE_DIR / "claims"
        agentd.CORRUPT_CLAIMS_DIR = agentd.STATE_DIR / "corrupt-claims"
        agentd.DAEMON_LOCK_PATH = agentd.STATE_DIR / "agentd.lock"
        agentd.REJECTED_UPDATE_PATH = agentd.STATE_DIR / "rejected-self-update.json"
        agentd.LOCAL_STATUS_PATH = agentd.STATE_DIR / "status.json"
        agentd.LOCAL_RUNS_DIR = agentd.STATE_DIR / "runs"
        agentd.core.CONTROL = root / "control"
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
        return {"id": task_id, "mode": "commands", "commands": ["true"]}

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

    def test_interrupted_attempt_is_terminal_failure(self) -> None:
        result = agentd.interrupted_result(
            "task-3",
            {
                "started_at": "2026-08-22T00:00:00+00:00",
                "task_digest": "abc",
                "attempt_id": "attempt",
            },
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failure_reason"], "interrupted_previous_attempt")
        self.assertEqual(result["task_digest"], "abc")
        self.assertIn("Automatic replay was blocked", result["error"])

    def test_corrupt_claim_is_terminal_and_never_replayed(self) -> None:
        task = self.task("task-corrupt")
        task_path = agentd.core.CONTROL / ".agent" / "tasks" / "task-corrupt.json"
        task_path.write_text(json.dumps(task), encoding="utf-8")
        claim_path = agentd.task_claim_path("task-corrupt")
        claim_path.parent.mkdir(parents=True, exist_ok=True)
        claim_path.write_text("{broken", encoding="utf-8")
        published: list[dict] = []

        def fake_publish(task_id, result):
            published.append(dict(result))
            result_path = agentd.core.CONTROL / ".agent" / "results" / f"{task_id}.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")

        with mock.patch.object(agentd.core, "publish_result", side_effect=fake_publish), mock.patch.object(
            agentd, "publish_run_state"
        ) as publish_run:
            agentd.recover_stale_claims()

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["status"], "failed")
        self.assertEqual(published[0]["failure_reason"], "corrupt_claim_state")
        self.assertIn("Automatic replay was blocked", published[0]["error"])
        self.assertFalse(claim_path.exists())
        self.assertEqual(len(list(agentd.CORRUPT_CLAIMS_DIR.glob("*.json"))), 1)
        self.assertEqual(agentd.pending_tasks(), [])
        self.assertTrue(publish_run.call_args.kwargs["force_remote"])

    def test_self_update_requires_clean_main_checkout(self) -> None:
        clean = mock.Mock(returncode=0, stdout="")
        dirty = mock.Mock(returncode=0, stdout="?? stray.py\n")
        main = mock.Mock(returncode=0, stdout="main\n")
        staging = mock.Mock(returncode=0, stdout="v4.2-staging\n")
        with mock.patch.object(agentd, "_git", return_value=clean):
            self.assertTrue(agentd.tracked_self_repo_clean())
        with mock.patch.object(agentd, "_git", return_value=dirty):
            self.assertFalse(agentd.tracked_self_repo_clean())
        with mock.patch.object(agentd, "_git", return_value=main):
            self.assertTrue(agentd.self_repo_on_main_branch())
        with mock.patch.object(agentd, "_git", return_value=staging):
            self.assertFalse(agentd.self_repo_on_main_branch())

    def test_invalid_task_file_becomes_terminal_result(self) -> None:
        path = agentd.core.CONTROL / ".agent" / "tasks" / "broken-task.json"
        path.write_text("{broken", encoding="utf-8")
        published: list[dict] = []

        def fake_publish(task_id, result):
            published.append(dict(result))
            result_path = agentd.core.CONTROL / ".agent" / "results" / f"{task_id}.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")

        with mock.patch.object(agentd.core, "publish_result", side_effect=fake_publish), mock.patch.object(
            agentd, "publish_run_state"
        ) as publish_run:
            agentd.recover_invalid_task_files()

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["id"], "broken-task")
        self.assertEqual(published[0]["failure_reason"], "invalid_task_file")
        self.assertEqual(agentd.pending_tasks(), [])
        self.assertTrue(publish_run.call_args.kwargs["force_remote"])

    def test_task_filename_must_match_payload_id(self) -> None:
        path = agentd.core.CONTROL / ".agent" / "tasks" / "filename-id.json"
        path.write_text(json.dumps(self.task("payload-id")), encoding="utf-8")
        published: list[dict] = []

        def fake_publish(task_id, result):
            published.append(dict(result))
            result_path = agentd.core.CONTROL / ".agent" / "results" / f"{task_id}.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")

        with mock.patch.object(agentd.core, "publish_result", side_effect=fake_publish), mock.patch.object(
            agentd, "publish_run_state"
        ) as publish_run:
            agentd.recover_invalid_task_files()

        self.assertEqual(published[0]["id"], "filename-id")
        self.assertEqual(published[0]["failure_reason"], "invalid_task_file")
        self.assertIn("filename/id mismatch", published[0]["error"])
        self.assertTrue(publish_run.call_args.kwargs["force_remote"])

    def test_progress_callback_persists_local_state(self) -> None:
        callback = agentd.make_progress_callback("task-4", "attempt", "digest")
        with mock.patch.object(agentd, "publish_control_json", return_value=True):
            callback(
                {
                    "event": "command_started",
                    "phase": "commands",
                    "index": 1,
                    "total": 2,
                    "command": "true",
                }
            )
        state = json.loads((agentd.LOCAL_RUNS_DIR / "task-4.json").read_text())
        self.assertEqual(state["task_id"], "task-4")
        self.assertEqual(state["attempt_id"], "attempt")
        self.assertEqual(state["event"], "command_started")

    def test_progress_callback_throttles_successful_command_boundaries(self) -> None:
        callback = agentd.make_progress_callback("task-5", "attempt", "digest")
        with mock.patch.object(agentd, "publish_run_state") as publish_run, mock.patch.object(
            agentd, "publish_daemon_status"
        ) as publish_status, mock.patch.object(
            agentd.time, "monotonic", side_effect=[100.0, 101.0, 102.0, 170.0]
        ):
            callback({"event": "task_started"})
            callback(
                {
                    "event": "command_started",
                    "phase": "commands",
                    "index": 1,
                    "total": 3,
                    "command": "one",
                }
            )
            callback(
                {
                    "event": "command_started",
                    "phase": "commands",
                    "index": 2,
                    "total": 3,
                    "command": "two",
                }
            )
            callback(
                {
                    "event": "command_started",
                    "phase": "commands",
                    "index": 3,
                    "total": 3,
                    "command": "three",
                }
            )

        remote_flags = [call.kwargs["force_remote"] for call in publish_run.call_args_list]
        self.assertEqual(remote_flags, [True, True, False, True])
        self.assertTrue(
            all(call.kwargs["force_remote"] is False for call in publish_status.call_args_list)
        )

    def test_failed_command_is_published_immediately(self) -> None:
        callback = agentd.make_progress_callback("task-6", "attempt", "digest")
        with mock.patch.object(agentd, "publish_run_state") as publish_run, mock.patch.object(
            agentd, "publish_daemon_status"
        ), mock.patch.object(agentd.time, "monotonic", side_effect=[100.0, 101.0]):
            callback({"event": "task_started"})
            callback(
                {
                    "event": "command_finished",
                    "phase": "commands",
                    "index": 1,
                    "total": 1,
                    "command": "false",
                    "exit_code": 1,
                    "elapsed_seconds": 0.1,
                }
            )

        self.assertTrue(publish_run.call_args_list[-1].kwargs["force_remote"])

    def test_long_successful_command_finish_is_published_immediately(self) -> None:
        callback = agentd.make_progress_callback("task-7", "attempt", "digest")
        with mock.patch.object(agentd, "publish_run_state") as publish_run, mock.patch.object(
            agentd, "publish_daemon_status"
        ), mock.patch.object(agentd.time, "monotonic", side_effect=[100.0, 101.0]):
            callback({"event": "task_started"})
            callback(
                {
                    "event": "command_finished",
                    "phase": "commands",
                    "index": 1,
                    "total": 1,
                    "command": "slow-success",
                    "exit_code": 0,
                    "elapsed_seconds": agentd.RUN_PROGRESS_SECONDS,
                }
            )

        self.assertTrue(publish_run.call_args_list[-1].kwargs["force_remote"])

    def test_remote_restart_control_is_acknowledged_before_restart(self) -> None:
        request_path = agentd.core.CONTROL / agentd.REMOTE_CONTROL_REQUEST
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_text(
            json.dumps({"id": "restart-1", "action": "restart"}),
            encoding="utf-8",
        )
        calls: list[str] = []

        def fake_publish(relative, payload, *, commit_message):
            calls.append(relative)
            ack = agentd.core.CONTROL / relative
            ack.parent.mkdir(parents=True, exist_ok=True)
            ack.write_text(json.dumps(payload), encoding="utf-8")
            return True

        with mock.patch.object(agentd, "publish_control_json", side_effect=fake_publish), mock.patch.object(
            agentd, "restart_self", side_effect=RuntimeError("restart called")
        ):
            with self.assertRaisesRegex(RuntimeError, "restart called"):
                agentd.handle_control_request()
        self.assertIn(".agent/daemon/acks/restart-1.json", calls)

    def test_v4_timeout_policy(self) -> None:
        self.assertEqual(agentd.core.COMMAND_TIMEOUT, 1200)
        self.assertEqual(agentd.core.MAX_COMMAND_TIMEOUT, 3600)
        self.assertEqual(agentd.runtime._idle_timeout, 600)


if __name__ == "__main__":
    unittest.main()
