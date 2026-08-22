from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import agentd


class AgentDaemonStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)

        self.originals = {
            "STATE_DIR": agentd.STATE_DIR,
            "CLAIMS_DIR": agentd.CLAIMS_DIR,
            "DAEMON_LOCK_PATH": agentd.DAEMON_LOCK_PATH,
            "REJECTED_UPDATE_PATH": agentd.REJECTED_UPDATE_PATH,
            "CONTROL": agentd.CONTROL,
        }

        agentd.STATE_DIR = root / "state"
        agentd.CLAIMS_DIR = agentd.STATE_DIR / "claims"
        agentd.DAEMON_LOCK_PATH = agentd.STATE_DIR / "agentd.lock"
        agentd.REJECTED_UPDATE_PATH = agentd.STATE_DIR / "rejected-self-update.json"
        agentd.CONTROL = root / "control"
        (agentd.CONTROL / ".agent" / "tasks").mkdir(parents=True)
        (agentd.CONTROL / ".agent" / "results").mkdir(parents=True)

    def tearDown(self) -> None:
        for name, value in self.originals.items():
            setattr(agentd, name, value)
        self.tmp.cleanup()

    def test_claim_is_atomic_and_blocks_replay(self) -> None:
        task_id = "task-123"
        self.assertTrue(agentd.claim_task(task_id))
        self.assertFalse(agentd.claim_task(task_id))
        self.assertTrue(agentd.task_claim_path(task_id).exists())

        agentd.release_task_claim(task_id)
        self.assertFalse(agentd.task_claim_path(task_id).exists())
        self.assertTrue(agentd.claim_task(task_id))

    def test_pending_tasks_skip_claimed_task(self) -> None:
        task = {"id": "task-claimed", "mode": "commands", "commands": ["true"]}
        task_path = agentd.CONTROL / ".agent" / "tasks" / "task-claimed.json"
        task_path.write_text(json.dumps(task), encoding="utf-8")

        self.assertEqual(len(agentd.pending_tasks()), 1)
        self.assertTrue(agentd.claim_task(task["id"]))
        self.assertEqual(agentd.pending_tasks(), [])

    def test_pending_tasks_skip_completed_task(self) -> None:
        task = {"id": "task-done", "mode": "commands", "commands": ["true"]}
        task_path = agentd.CONTROL / ".agent" / "tasks" / "task-done.json"
        task_path.write_text(json.dumps(task), encoding="utf-8")
        result_path = agentd.CONTROL / ".agent" / "results" / "task-done.json"
        result_path.write_text(json.dumps({"id": "task-done", "status": "done"}), encoding="utf-8")

        self.assertEqual(agentd.pending_tasks(), [])

    def test_interrupted_result_is_terminal_failure(self) -> None:
        result = agentd.interrupted_result(
            "task-interrupted",
            {"started_at": "2026-08-22T00:00:00+00:00"},
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failure_reason"], "interrupted_previous_attempt")
        self.assertIn("Automatic replay was blocked", result["error"])


class AgentDaemonTimeoutTests(unittest.TestCase):
    def test_default_timeout_is_bounded(self) -> None:
        self.assertEqual(agentd.command_timeout_for({}), 1200)

    def test_timeout_above_maximum_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            agentd.command_timeout_for({"command_timeout": agentd.MAX_COMMAND_TIMEOUT + 1})

    def test_explicit_timeout_at_maximum_is_allowed(self) -> None:
        self.assertEqual(
            agentd.command_timeout_for({"command_timeout": agentd.MAX_COMMAND_TIMEOUT}),
            agentd.MAX_COMMAND_TIMEOUT,
        )


if __name__ == "__main__":
    unittest.main()
