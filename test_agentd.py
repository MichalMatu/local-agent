from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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
            "CONTROL": agentd.core.CONTROL,
        }
        agentd.STATE_DIR = root / "state"
        agentd.CLAIMS_DIR = agentd.STATE_DIR / "claims"
        agentd.DAEMON_LOCK_PATH = agentd.STATE_DIR / "agentd.lock"
        agentd.REJECTED_UPDATE_PATH = agentd.STATE_DIR / "rejected-self-update.json"
        agentd.core.CONTROL = root / "control"
        (agentd.core.CONTROL / ".agent" / "tasks").mkdir(parents=True)
        (agentd.core.CONTROL / ".agent" / "results").mkdir(parents=True)

    def tearDown(self) -> None:
        agentd.STATE_DIR = self.originals["STATE_DIR"]
        agentd.CLAIMS_DIR = self.originals["CLAIMS_DIR"]
        agentd.DAEMON_LOCK_PATH = self.originals["DAEMON_LOCK_PATH"]
        agentd.REJECTED_UPDATE_PATH = self.originals["REJECTED_UPDATE_PATH"]
        agentd.core.CONTROL = self.originals["CONTROL"]
        self.tmp.cleanup()

    def test_claim_blocks_duplicate_execution(self) -> None:
        self.assertTrue(agentd.claim_task("task-1"))
        self.assertFalse(agentd.claim_task("task-1"))
        agentd.release_task_claim("task-1")
        self.assertTrue(agentd.claim_task("task-1"))

    def test_pending_queue_skips_claimed_task(self) -> None:
        task = {"id": "task-2", "mode": "commands", "commands": ["true"]}
        path = agentd.core.CONTROL / ".agent" / "tasks" / "task-2.json"
        path.write_text(json.dumps(task), encoding="utf-8")
        self.assertEqual(len(agentd.pending_tasks()), 1)
        self.assertTrue(agentd.claim_task("task-2"))
        self.assertEqual(agentd.pending_tasks(), [])

    def test_interrupted_attempt_is_terminal_failure(self) -> None:
        result = agentd.interrupted_result(
            "task-3",
            {"started_at": "2026-08-22T00:00:00+00:00"},
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failure_reason"], "interrupted_previous_attempt")
        self.assertIn("Automatic replay was blocked", result["error"])

    def test_default_and_maximum_command_timeout(self) -> None:
        self.assertEqual(agentd.core.command_timeout_for({}), 1200)
        self.assertEqual(
            agentd.core.command_timeout_for({"command_timeout": 3600}),
            3600,
        )
        with self.assertRaises(ValueError):
            agentd.core.command_timeout_for({"command_timeout": 3601})


if __name__ == "__main__":
    unittest.main()
