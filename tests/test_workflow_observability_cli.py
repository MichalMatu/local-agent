from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from local_agent.cli import workflow
from local_agent.workflow import contract
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore


BINDING = "00000000-0000-4000-8000-000000000151"
WORKFLOW_ID = "observability-cli"


def task_node(node_id: str, depends_on: list[str]) -> dict:
    return {
        "id": node_id,
        "kind": "task",
        "repository_id": "repo-a",
        "agent_binding": BINDING,
        "depends_on": depends_on,
        "task": {
            "work_branch": "main",
            "allow_write": False,
            "resources": [],
            "commands": ["true"],
        },
    }


def base_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": WORKFLOW_ID,
        "created_at": "2026-09-19T15:50:00Z",
        "nodes": [
            task_node("audit", []),
            {
                "id": "review-audit",
                "kind": "planner_checkpoint",
                "depends_on": ["audit"],
            },
        ],
    }


def revision_one(base: dict) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "revision": 1,
        "created_at": "2026-09-19T15:51:00Z",
        "parent_digest": contract.manifest_digest(base),
        "checkpoint_node_id": "review-audit",
        "nodes": [task_node("implement", ["review-audit"])],
    }


class WorkflowObservabilityCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with mock.patch("sys.argv", ["workflow", *args]), redirect_stdout(output):
            code = workflow.main()
        return code, output.getvalue()

    def test_activations_and_effective_state_commands_are_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"
            workflow_store = WorkflowStore(state_dir)
            base = base_manifest()
            workflow_store.submit(base)
            for target in ("dispatched", "running", "succeeded"):
                workflow_store.set_node_state(WORKFLOW_ID, "audit", target)
            resolution = workflow_store.resolve_planner_checkpoint(
                WORKFLOW_ID,
                "review-audit",
                resolver="chatgpt-planner",
            )
            revision_store = WorkflowRevisionStore(workflow_store)
            first = revision_one(base)
            revision_store.append(WORKFLOW_ID, first)
            activation_store = WorkflowRevisionActivationStore(
                workflow_store,
                revision_store,
            )
            base_states = dict(workflow_store.load_state(WORKFLOW_ID)["node_states"])
            activation_store.append(
                WORKFLOW_ID,
                1,
                base_states,
                resolution,
                activated_at="2026-09-19T15:52:00Z",
            )
            effective_store = WorkflowEffectiveStateStore(
                workflow_store,
                revision_store,
                activation_store,
            )
            effective_store.initialize(WORKFLOW_ID)

            workflow_root = state_dir / "workflows" / WORKFLOW_ID
            observed_paths = [
                workflow_root / "manifest.json",
                workflow_root / "state.json",
                workflow_root / "revisions" / "000001.json",
                workflow_root / "activations" / "000001.json",
                workflow_root / "effective_state.json",
            ]
            before = {path: path.read_bytes() for path in observed_paths}
            prefix = ("--state-dir", str(state_dir))

            code, output = self.run_cli(*prefix, "activations", WORKFLOW_ID)
            self.assertEqual(code, 0)
            activations = json.loads(output)
            self.assertEqual(activations["activation_count"], 1)
            self.assertEqual(activations["activations"][0]["revision"], 1)
            self.assertEqual(
                activations["activations"][0]["checkpoint_node_id"],
                "review-audit",
            )

            code, output = self.run_cli(*prefix, "effective-state", WORKFLOW_ID)
            self.assertEqual(code, 0)
            effective = json.loads(output)["effective_state"]
            self.assertEqual(effective["active_revision"], 1)
            self.assertEqual(effective["node_states"]["implement"], "ready")
            self.assertFalse(effective["cancel_requested"])

            after = {path: path.read_bytes() for path in observed_paths}
            self.assertEqual(after, before)
            self.assertFalse((Path(directory) / "repo-a").exists())


if __name__ == "__main__":
    unittest.main()
