from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from local_agent.cli import workflow
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore
from tests import test_workflow_activation as activation_fixture
from tests import test_workflow_effective_controls as controls_fixture


class WorkflowOperatorCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with mock.patch("sys.argv", ["workflow", *args]), redirect_stdout(output):
            code = workflow.main()
        return code, output.getvalue()

    def test_activate_next_initializes_first_effective_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"
            workflow_store = WorkflowStore(state_dir)
            base = activation_fixture.base_manifest()
            workflow_store.submit(base)
            revision_store = WorkflowRevisionStore(workflow_store)
            first = activation_fixture.revision_one(base)
            revision_store.append(base["id"], first)
            for target in ("dispatched", "running", "succeeded"):
                workflow_store.set_node_state(base["id"], "audit", target)
            workflow_store.resolve_planner_checkpoint(
                base["id"],
                "review",
                resolver="chatgpt-planner",
                note="Continue.",
            )

            code, output = self.run_cli(
                "--state-dir",
                str(state_dir),
                "activate-next",
                base["id"],
            )

            self.assertEqual(code, 0)
            payload = json.loads(output)
            self.assertEqual(payload["activation"]["revision"], 1)
            self.assertEqual(payload["effective_state"]["active_revision"], 1)
            self.assertEqual(
                payload["effective_state"]["node_states"]["implement"],
                "ready",
            )

    def test_effective_checkpoint_then_second_activation_is_explicit_and_contiguous(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"
            workflow_store = WorkflowStore(state_dir)
            base = activation_fixture.base_manifest()
            workflow_store.submit(base)
            revision_store = WorkflowRevisionStore(workflow_store)
            first = activation_fixture.revision_one(base)
            revision_store.append(base["id"], first)
            for target in ("dispatched", "running", "succeeded"):
                workflow_store.set_node_state(base["id"], "audit", target)
            workflow_store.resolve_planner_checkpoint(
                base["id"],
                "review",
                resolver="chatgpt-planner",
            )
            code, _ = self.run_cli(
                "--state-dir",
                str(state_dir),
                "activate-next",
                base["id"],
            )
            self.assertEqual(code, 0)

            effective_store = WorkflowEffectiveStateStore(WorkflowStore(state_dir))
            for target in ("dispatched", "running", "succeeded"):
                effective_store.set_task_node_state(base["id"], "implement", target)

            code, output = self.run_cli(
                "--state-dir",
                str(state_dir),
                "resolve-effective-checkpoint",
                base["id"],
                "implementation-review",
                "--resolver",
                "chatgpt-planner",
                "--note",
                "Implementation accepted.",
            )
            self.assertEqual(code, 0)
            resolved = json.loads(output)
            self.assertEqual(
                resolved["resolution"]["node_id"],
                "implementation-review",
            )

            second = activation_fixture.revision_two(base, first)
            revision_store.append(base["id"], second)
            code, output = self.run_cli(
                "--state-dir",
                str(state_dir),
                "activate-next",
                base["id"],
            )
            self.assertEqual(code, 0)
            activated = json.loads(output)
            self.assertEqual(activated["activation"]["revision"], 2)
            self.assertEqual(activated["effective_state"]["active_revision"], 2)
            self.assertEqual(
                activated["effective_state"]["node_states"]["verify"],
                "ready",
            )

    def test_effective_cancel_mutates_effective_state_not_base_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"
            workflow_store = WorkflowStore(state_dir)
            base = activation_fixture.base_manifest()
            workflow_store.submit(base)
            revision_store = WorkflowRevisionStore(workflow_store)
            revision_store.append(base["id"], activation_fixture.revision_one(base))
            for target in ("dispatched", "running", "succeeded"):
                workflow_store.set_node_state(base["id"], "audit", target)
            workflow_store.resolve_planner_checkpoint(
                base["id"],
                "review",
                resolver="chatgpt-planner",
            )
            code, _ = self.run_cli(
                "--state-dir",
                str(state_dir),
                "activate-next",
                base["id"],
            )
            self.assertEqual(code, 0)
            base_before = workflow_store.load_state(base["id"])

            code, output = self.run_cli(
                "--state-dir",
                str(state_dir),
                "cancel-effective",
                base["id"],
            )

            self.assertEqual(code, 0)
            payload = json.loads(output)
            self.assertTrue(payload["effective_state"]["cancel_requested"])
            self.assertEqual(payload["effective_state"]["workflow_state"], "cancelled")
            self.assertEqual(workflow_store.load_state(base["id"]), base_before)

    def test_effective_user_gate_can_be_resolved_from_operator_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"
            workflow_store = WorkflowStore(state_dir)
            base = controls_fixture.base_manifest()
            workflow_store.submit(base)
            revision_store = WorkflowRevisionStore(workflow_store)
            revision_store.append(base["id"], controls_fixture.revision_one(base))
            for target in ("dispatched", "running", "succeeded"):
                workflow_store.set_node_state(base["id"], "audit", target)
            workflow_store.resolve_planner_checkpoint(
                base["id"],
                "review-audit",
                resolver="chatgpt-planner",
            )
            code, _ = self.run_cli(
                "--state-dir",
                str(state_dir),
                "activate-next",
                base["id"],
            )
            self.assertEqual(code, 0)

            effective_store = WorkflowEffectiveStateStore(WorkflowStore(state_dir))
            for target in ("dispatched", "running", "succeeded"):
                effective_store.set_task_node_state(base["id"], "implement", target)

            code, output = self.run_cli(
                "--state-dir",
                str(state_dir),
                "resolve-effective-gate",
                base["id"],
                "approve-release",
                "approve",
                "--resolver",
                "local-operator",
            )

            self.assertEqual(code, 0)
            payload = json.loads(output)
            self.assertEqual(payload["decision"]["decision"], "approve")
            self.assertEqual(
                payload["effective_state"]["node_states"]["release"],
                "ready",
            )


if __name__ == "__main__":
    unittest.main()
