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
            "DAEMON_LOCK_PATH": agentd.DAEMON_LOCK_PATH,
            "REJECTED_UPDATE_PATH": agentd.REJECTED_UPDATE_PATH,
            "LOCAL_STATUS_PATH": agentd.LOCAL_STATUS_PATH,
            "LOCAL_RUNS_DIR": agentd.LOCAL_RUNS_DIR,
            "CONTROL": agentd.core.CONTROL,
        }
        agentd.STATE_DIR = root / "state"
        agentd.CLAIMS_DIR = agentd.STATE_DIR / "claims"
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
