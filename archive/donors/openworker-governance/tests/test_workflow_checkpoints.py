from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_agent.workflow.store import WorkflowStore


FIXTURE = Path(__file__).parent / "fixtures" / "workflows" / "planner_checkpoint.json"


def manifest() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class WorkflowCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name) / "state"
        self.store = WorkflowStore(self.state_dir)
        self.workflow = manifest()
        self.store.submit(self.workflow)
        self.store.set_node_state(self.workflow["id"], "audit", "succeeded")
        state = self.store.load_state(self.workflow["id"])
        self.assertEqual(state["node_states"]["review"], "waiting_planner")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_resolve_checkpoint_persists_provenance_and_completes_node(self) -> None:
        resolution = self.store.resolve_planner_checkpoint(
            self.workflow["id"],
            "review",
            resolver="chatgpt-planner",
            note="Audit evidence reviewed; continue.",
        )
        self.assertEqual(resolution["resolver"], "chatgpt-planner")
        self.assertEqual(resolution["note"], "Audit evidence reviewed; continue.")
        self.assertEqual(
            self.store.load_planner_checkpoint_resolution(
                self.workflow["id"],
                "review",
            ),
            resolution,
        )
        state = self.store.load_state(self.workflow["id"])
        self.assertEqual(state["node_states"]["review"], "succeeded")
        self.assertEqual(state["workflow_state"], "completed")

    def test_repeated_resolution_is_idempotent_and_first_resolver_wins(self) -> None:
        first = self.store.resolve_planner_checkpoint(
            self.workflow["id"],
            "review",
            resolver="planner-a",
            note="first",
        )
        second = self.store.resolve_planner_checkpoint(
            self.workflow["id"],
            "review",
            resolver="planner-b",
            note="second",
        )
        self.assertEqual(second, first)
        self.assertEqual(second["resolver"], "planner-a")
        self.assertEqual(second["note"], "first")

    def test_resolution_and_node_transition_are_one_atomic_state_write(self) -> None:
        original = self.store.load_state(self.workflow["id"])
        with mock.patch(
            "local_agent.workflow.store.atomic_write_text",
            side_effect=RuntimeError("simulated atomic write failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated atomic write failure"):
                self.store.resolve_planner_checkpoint(
                    self.workflow["id"],
                    "review",
                    resolver="planner",
                )

        restarted = WorkflowStore(self.state_dir)
        self.assertEqual(restarted.load_state(self.workflow["id"]), original)
        self.assertIsNone(
            restarted.load_planner_checkpoint_resolution(
                self.workflow["id"],
                "review",
            )
        )

        resolution = restarted.resolve_planner_checkpoint(
            self.workflow["id"],
            "review",
            resolver="planner",
        )
        self.assertIsNone(resolution["note"])
        self.assertEqual(
            restarted.load_state(self.workflow["id"])["node_states"]["review"],
            "succeeded",
        )

    def test_resolution_after_cancel_is_rejected(self) -> None:
        self.store.cancel(self.workflow["id"])
        with self.assertRaisesRegex(ValueError, "not waiting for planner"):
            self.store.resolve_planner_checkpoint(
                self.workflow["id"],
                "review",
                resolver="planner",
            )

    def test_non_checkpoint_node_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a planner checkpoint"):
            self.store.resolve_planner_checkpoint(
                self.workflow["id"],
                "audit",
                resolver="planner",
            )

    def test_note_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "checkpoint note"):
            self.store.resolve_planner_checkpoint(
                self.workflow["id"],
                "review",
                resolver="planner",
                note="x" * 4097,
            )


if __name__ == "__main__":
    unittest.main()
