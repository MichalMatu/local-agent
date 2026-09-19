from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_agent.workflow.store import WorkflowStore


FIXTURE = Path(__file__).parent / "fixtures" / "workflows" / "single_repo.json"


class WorkflowStoreAuditTests(unittest.TestCase):
    def test_audit_append_failure_does_not_reverse_committed_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowStore(Path(directory))
            manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
            store.submit(manifest)

            with mock.patch.object(
                store,
                "_append_event",
                side_effect=OSError("simulated audit disk failure"),
            ):
                updated = store.set_node_state(
                    manifest["id"],
                    "build",
                    "dispatched",
                )

            self.assertEqual(updated["node_states"]["build"], "dispatched")
            restarted = WorkflowStore(Path(directory))
            persisted = restarted.load_state(manifest["id"])
            self.assertEqual(persisted["node_states"]["build"], "dispatched")

    def test_gate_resolution_remains_authoritative_when_audit_append_fails(self) -> None:
        gate_fixture = Path(__file__).parent / "fixtures" / "workflows" / "user_gate.json"
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowStore(Path(directory))
            manifest = json.loads(gate_fixture.read_text(encoding="utf-8"))
            store.submit(manifest)
            store.set_node_state(manifest["id"], "audit", "succeeded")

            with mock.patch.object(
                store,
                "_append_event",
                side_effect=OSError("simulated audit disk failure"),
            ):
                decision = store.resolve_user_gate(
                    manifest["id"],
                    "choice",
                    "preserve_compat",
                    resolver="test",
                )

            self.assertEqual(decision["decision"], "preserve_compat")
            persisted = WorkflowStore(Path(directory)).load_state(manifest["id"])
            self.assertEqual(persisted["node_states"]["choice"], "succeeded")
            self.assertEqual(
                persisted["gate_decisions"]["choice"]["decision"],
                "preserve_compat",
            )


if __name__ == "__main__":
    unittest.main()
