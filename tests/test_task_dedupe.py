from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.supervisor import task_dedupe


class TaskDedupeTests(unittest.TestCase):
    def task(self, task_id: str, command: str = "true") -> dict[str, object]:
        return {
            "id": task_id,
            "agent_binding": "3da0947d-9acf-4ecf-adce-a29be7dc5c09",
            "mode": "commands",
            "work_branch": "main",
            "allow_write": True,
            "resources": [],
            "task_timeout": 1800,
            "steps": [
                {
                    "name": f"stage-{task_id}",
                    "command": command,
                    "timeout": 120,
                    "output_policy": "summary",
                }
            ],
        }

    def test_execution_fingerprint_ignores_identity_and_cosmetic_stage_metadata(self) -> None:
        first = self.task("task-a")
        second = self.task("task-b")
        second["command_timeout"] = 900
        second["output_policy"] = "stream"
        second["steps"] = [
            {
                "name": "renamed-stage",
                "command": "true",
                "timeout": 30,
                "output_policy": "stream",
            }
        ]

        self.assertEqual(
            task_dedupe.execution_fingerprint(first),
            task_dedupe.execution_fingerprint(second),
        )

    def test_execution_fingerprint_changes_when_effect_changes(self) -> None:
        self.assertNotEqual(
            task_dedupe.execution_fingerprint(self.task("task-a", "true")),
            task_dedupe.execution_fingerprint(self.task("task-b", "false")),
        )

    def test_explicit_dedupe_key_is_canonical_and_stable(self) -> None:
        first = self.task("task-a", "first")
        second = self.task("task-b", "second")
        first["dedupe_key"] = "growclip:main:telegram:worker-quality"
        second["dedupe_key"] = "growclip:main:telegram:worker-quality"

        self.assertEqual(task_dedupe.queue_key(first), task_dedupe.queue_key(second))
        with self.assertRaisesRegex(ValueError, "canonical"):
            task_dedupe.queue_key({**first, "dedupe_key": " bad "})
        with self.assertRaisesRegex(ValueError, "unsupported"):
            task_dedupe.queue_key({**first, "dedupe_key": "bad key"})

    def test_plan_suppresses_same_effect_with_different_task_ids(self) -> None:
        pending = [
            (Path("a.json"), self.task("task-a")),
            (Path("b.json"), self.task("task-b")),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            plan = task_dedupe.plan_pending(Path(tmp), pending, now_epoch=100.0)

        self.assertEqual([item[1]["id"] for item in plan.candidates], ["task-a"])
        self.assertEqual(len(plan.suppressed), 1)
        self.assertEqual(plan.suppressed[0].duplicate_of, "task-a")
        self.assertEqual(plan.suppressed[0].reason, "queued_duplicate")

    def test_explicit_intent_key_suppresses_different_plans_for_same_goal(self) -> None:
        first = self.task("task-a", "first-plan")
        second = self.task("task-b", "different-plan")
        first["dedupe_key"] = "growclip:main:nodeflow:diagnostics"
        second["dedupe_key"] = "growclip:main:nodeflow:diagnostics"
        pending = [(Path("a.json"), first), (Path("b.json"), second)]

        with tempfile.TemporaryDirectory() as tmp:
            plan = task_dedupe.plan_pending(Path(tmp), pending, now_epoch=100.0)

        self.assertEqual([item[1]["id"] for item in plan.candidates], ["task-a"])
        self.assertEqual(plan.suppressed[0].duplicate_of, "task-a")

    def test_recent_admission_suppresses_late_duplicate_from_another_chat(self) -> None:
        first = self.task("task-a")
        second = self.task("task-b")
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            task_dedupe.record_admission(state_dir, first, now_epoch=100.0)
            plan = task_dedupe.plan_pending(
                state_dir,
                [(Path("b.json"), second)],
                now_epoch=101.0,
            )

        self.assertEqual(plan.candidates, ())
        self.assertEqual(plan.suppressed[0].duplicate_of, "task-a")
        self.assertEqual(plan.suppressed[0].reason, "recent_duplicate")

    def test_receipt_for_same_task_does_not_suppress_resource_retry(self) -> None:
        task = self.task("task-a")
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            task_dedupe.record_admission(state_dir, task, now_epoch=100.0)
            plan = task_dedupe.plan_pending(
                state_dir,
                [(Path("a.json"), task)],
                now_epoch=101.0,
            )

        self.assertEqual([item[1]["id"] for item in plan.candidates], ["task-a"])
        self.assertEqual(plan.suppressed, ())

    def test_completion_receipt_expires_after_bounded_window(self) -> None:
        first = self.task("task-a")
        second = self.task("task-b")
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            task_dedupe.record_completion(state_dir, first, "published", now_epoch=100.0)
            recent = task_dedupe.plan_pending(
                state_dir,
                [(Path("b.json"), second)],
                now_epoch=100.0 + task_dedupe.RECENT_COMPLETION_TTL_SECONDS - 1,
            )
            expired = task_dedupe.plan_pending(
                state_dir,
                [(Path("b.json"), second)],
                now_epoch=100.0 + task_dedupe.RECENT_COMPLETION_TTL_SECONDS + 1,
            )

        self.assertEqual(recent.candidates, ())
        self.assertEqual([item[1]["id"] for item in expired.candidates], ["task-b"])


if __name__ == "__main__":
    unittest.main()
