from __future__ import annotations

import json
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from local_agent.foundation import result_events


class ResultEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = self.root / "control"
        binding = self.control / ".agent" / "binding.json"
        binding.parent.mkdir(parents=True)
        binding.write_text(
            json.dumps(
                {
                    "version": 1,
                    "repository_id": "tracker",
                    "repository": "MichalMatu/tracker",
                    "agent_binding": "be481b25-9d97-4205-b93f-95f5c5827441",
                }
            ),
            encoding="utf-8",
        )
        self.state_dir = self.root / "state"

    def test_record_ack_and_identity_are_bounded(self) -> None:
        result = {
            "id": "task-1",
            "status": "done",
            "task_digest": "abc123",
        }
        event = result_events.record_published_result(
            control_dir=self.control,
            task_id="task-1",
            result=result,
            state_dir=self.state_dir,
        )
        self.assertEqual(event["event_type"], "task_result_ready")
        self.assertEqual(event["repository_id"], "tracker")
        self.assertEqual(event["repository"], "MichalMatu/tracker")
        self.assertEqual(event["agent_binding"], "be481b25-9d97-4205-b93f-95f5c5827441")
        self.assertEqual(event["task_id"], "task-1")
        self.assertEqual(event["result_status"], "done")
        self.assertEqual(event["task_digest"], "abc123")
        self.assertLessEqual(
            len(json.dumps(event, ensure_ascii=False).encode("utf-8")),
            result_events.MAX_EVENT_BYTES,
        )

        pending = result_events.pending_events(state_dir=self.state_dir)
        self.assertEqual([item["event_id"] for item in pending], [event["event_id"]])
        self.assertTrue(
            result_events.acknowledge_event(event["event_id"], state_dir=self.state_dir)
        )
        self.assertEqual(result_events.pending_events(state_dir=self.state_dir), [])
        self.assertFalse(
            result_events.acknowledge_event(event["event_id"], state_dir=self.state_dir)
        )

    def test_repeated_publication_is_idempotent(self) -> None:
        result = {"id": "task-2", "status": "failed", "task_digest": "digest-2"}
        first_at = datetime.now().astimezone()
        first = result_events.build_result_event(
            control_dir=self.control,
            task_id="task-2",
            result=result,
            emitted_at=first_at.isoformat(),
        )
        result_events.enqueue_event(first, state_dir=self.state_dir)
        second = result_events.build_result_event(
            control_dir=self.control,
            task_id="task-2",
            result=result,
            emitted_at=(first_at + timedelta(seconds=1)).isoformat(),
        )
        path = result_events.enqueue_event(second, state_dir=self.state_dir)
        stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["event_id"], first["event_id"])
        self.assertEqual(stored["emitted_at"], first["emitted_at"])
        self.assertEqual(len(result_events.pending_events(state_dir=self.state_dir)), 1)

    def test_same_event_id_with_changed_terminal_identity_is_rejected(self) -> None:
        result = {"id": "task-3", "status": "done", "task_digest": "digest-3"}
        event = result_events.build_result_event(
            control_dir=self.control,
            task_id="task-3",
            result=result,
        )
        result_events.enqueue_event(event, state_dir=self.state_dir)
        conflicting = dict(event, result_status="failed")
        with self.assertRaisesRegex(ValueError, "invalid result event payload|event id collision"):
            result_events.enqueue_event(conflicting, state_dir=self.state_dir)

    def test_invalid_control_binding_fails_closed(self) -> None:
        binding = self.control / ".agent" / "binding.json"
        payload = json.loads(binding.read_text(encoding="utf-8"))
        payload["agent_binding"] = "NOT-A-UUID"
        binding.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "canonical UUID"):
            result_events.build_result_event(
                control_dir=self.control,
                task_id="task-4",
                result={"id": "task-4", "status": "done"},
            )

    def test_prune_removes_expired_event(self) -> None:
        event = result_events.build_result_event(
            control_dir=self.control,
            task_id="task-old",
            result={"id": "task-old", "status": "done"},
            emitted_at=result_events.now_iso(),
        )
        result_events.enqueue_event(event, state_dir=self.state_dir)
        future = time.time() + result_events.EVENT_TTL_SECONDS + 1
        removed = result_events.prune_outbox(state_dir=self.state_dir, now=future)
        self.assertIn(f"{event['event_id']}.json", removed)
        self.assertEqual(result_events.pending_events(state_dir=self.state_dir), [])

    def test_prune_removes_tampered_payload_with_valid_filename(self) -> None:
        event = result_events.build_result_event(
            control_dir=self.control,
            task_id="task-tampered",
            result={"id": "task-tampered", "status": "done", "task_digest": "digest-ok"},
        )
        path = result_events.enqueue_event(event, state_dir=self.state_dir)
        tampered = dict(event)
        tampered["task_id"] = "different-task"
        path.write_text(json.dumps(tampered), encoding="utf-8")

        removed = result_events.prune_outbox(state_dir=self.state_dir)

        self.assertIn(path.name, removed)
        self.assertFalse(path.exists())
        self.assertEqual(result_events.pending_events(state_dir=self.state_dir), [])

    def test_enqueue_rejects_event_id_not_derived_from_payload_identity(self) -> None:
        event = result_events.build_result_event(
            control_dir=self.control,
            task_id="task-derived-id",
            result={"id": "task-derived-id", "status": "done"},
        )
        event["event_id"] = "evt-" + "f" * 32
        with self.assertRaisesRegex(ValueError, "invalid result event payload"):
            result_events.enqueue_event(event, state_dir=self.state_dir)

    def test_prune_bounds_event_count_oldest_first(self) -> None:
        base = datetime.now(timezone.utc)
        events: list[dict[str, object]] = []
        with mock.patch.object(result_events, "MAX_OUTBOX_EVENTS", 3):
            for index in range(4):
                task_id = f"bounded-{index}"
                event = result_events.build_result_event(
                    control_dir=self.control,
                    task_id=task_id,
                    result={"id": task_id, "status": "done", "task_digest": f"digest-{index}"},
                    emitted_at=(base + timedelta(seconds=index)).isoformat(),
                )
                result_events.enqueue_event(event, state_dir=self.state_dir)
                events.append(event)

            pending = result_events.pending_events(state_dir=self.state_dir)

        self.assertEqual(len(pending), 3)
        self.assertNotIn(events[0]["event_id"], {event["event_id"] for event in pending})
        self.assertEqual(
            [event["task_id"] for event in pending],
            ["bounded-1", "bounded-2", "bounded-3"],
        )

    def test_prune_removes_symlink_event_without_following_target(self) -> None:
        event = result_events.build_result_event(
            control_dir=self.control,
            task_id="symlink-event",
            result={"id": "symlink-event", "status": "done"},
        )
        directory = result_events.outbox_dir(self.state_dir)
        directory.mkdir(parents=True, exist_ok=True)
        target = self.root / "outside.json"
        target.write_text(json.dumps(event), encoding="utf-8")
        link = directory / f"{event['event_id']}.json"
        link.symlink_to(target)

        removed = result_events.prune_outbox(state_dir=self.state_dir)

        self.assertIn(link.name, removed)
        self.assertFalse(link.exists())
        self.assertTrue(target.exists(), "pruning a symlink must not delete its target")


if __name__ == "__main__":
    unittest.main()
