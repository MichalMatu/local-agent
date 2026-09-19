from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_agent.workflow.store import WorkflowStore


FIXTURE = Path(__file__).parent / "fixtures" / "workflows" / "user_gate.json"


def manifest() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class WorkflowGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name) / "state"
        self.store = WorkflowStore(self.state_dir)
        self.workflow = manifest()
        self.store.submit(self.workflow)
        self.store.set_node_state(self.workflow["id"], "audit", "succeeded")
        state = self.store.load_state(self.workflow["id"])
        self.assertEqual(state["node_states"]["choice"], "waiting_user")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_resolve_gate_persists_decision_and_completes_node(self) -> None:
        decision = self.store.resolve_user_gate(
            self.workflow["id"],
            "choice",
            "preserve_compat",
            resolver="local-operator",
        )
        self.assertEqual(decision["decision"], "preserve_compat")
        self.assertEqual(decision["resolver"], "local-operator")
        loaded = self.store.load_gate_decision(self.workflow["id"], "choice")
        self.assertEqual(loaded, decision)
        state = self.store.load_state(self.workflow["id"])
        self.assertEqual(state["node_states"]["choice"], "succeeded")
        self.assertEqual(state["workflow_state"], "completed")

    def test_same_decision_is_idempotent_and_first_resolver_wins(self) -> None:
        first = self.store.resolve_user_gate(
            self.workflow["id"],
            "choice",
            "preserve_compat",
            resolver="operator-a",
        )
        second = self.store.resolve_user_gate(
            self.workflow["id"],
            "choice",
            "preserve_compat",
            resolver="operator-b",
        )
        self.assertEqual(second, first)
        self.assertEqual(second["resolver"], "operator-a")

    def test_conflicting_second_decision_is_rejected(self) -> None:
        self.store.resolve_user_gate(
            self.workflow["id"],
            "choice",
            "preserve_compat",
            resolver="operator-a",
        )
        with self.assertRaisesRegex(ValueError, "already resolved"):
            self.store.resolve_user_gate(
                self.workflow["id"],
                "choice",
                "allow_breaking",
                resolver="operator-b",
            )

    def test_invalid_choice_is_rejected_without_decision_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "not an allowed choice"):
            self.store.resolve_user_gate(
                self.workflow["id"],
                "choice",
                "invalid",
                resolver="operator",
            )
        self.assertIsNone(self.store.load_gate_decision(self.workflow["id"], "choice"))
        state = self.store.load_state(self.workflow["id"])
        self.assertEqual(state["node_states"]["choice"], "waiting_user")

    def test_decision_record_survives_crash_before_state_transition(self) -> None:
        with mock.patch.object(
            self.store,
            "set_node_state",
            side_effect=RuntimeError("simulated crash after decision write"),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                self.store.resolve_user_gate(
                    self.workflow["id"],
                    "choice",
                    "preserve_compat",
                    resolver="operator",
                )

        restarted = WorkflowStore(self.state_dir)
        recorded = restarted.load_gate_decision(self.workflow["id"], "choice")
        self.assertIsNotNone(recorded)
        state = restarted.load_state(self.workflow["id"])
        self.assertEqual(state["node_states"]["choice"], "waiting_user")

        recovered = restarted.resolve_user_gate(
            self.workflow["id"],
            "choice",
            "preserve_compat",
            resolver="different-resolver",
        )
        self.assertEqual(recovered, recorded)
        self.assertEqual(
            restarted.load_state(self.workflow["id"])["node_states"]["choice"],
            "succeeded",
        )

    def test_gate_resolution_after_workflow_cancel_is_rejected(self) -> None:
        self.store.cancel(self.workflow["id"])
        with self.assertRaisesRegex(ValueError, "not waiting for user"):
            self.store.resolve_user_gate(
                self.workflow["id"],
                "choice",
                "preserve_compat",
                resolver="operator",
            )


if __name__ == "__main__":
    unittest.main()
