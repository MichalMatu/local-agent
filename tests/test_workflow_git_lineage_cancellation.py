from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import contract, publishing
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.git_cancellation import GitWorkflowCancellationTransport
from local_agent.workflow.git_control_plane import GitWorkflowControlPlane
from local_agent.workflow.lineage_cycle import run_lineage_cycle
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore
from tests.test_workflow_git_control_plane import (
    BINDINGS,
    init_remote,
    publish_from_seed,
    remote_json,
    run_git,
)


WORKFLOW_ID = "git-lineage-cancellation"
BINDING = BINDINGS["repo-a"]


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
        "created_at": "2026-09-19T16:00:00Z",
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
        "created_at": "2026-09-19T16:01:00Z",
        "parent_digest": contract.manifest_digest(base),
        "checkpoint_node_id": "review-audit",
        "nodes": [
            task_node("implement", ["review-audit"]),
            {
                "id": "review-implementation",
                "kind": "planner_checkpoint",
                "depends_on": ["implement"],
            },
        ],
    }


class WorkflowGitLineageCancellationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repository, self.origin, self.seed = init_remote(self.root, "repo-a")

        self.workflow_store = WorkflowStore(self.root / "state")
        self.base = base_manifest()
        self.workflow_store.submit(self.base)
        self.revision_store = WorkflowRevisionStore(self.workflow_store)
        self.activation_store = WorkflowRevisionActivationStore(
            self.workflow_store,
            self.revision_store,
        )
        self.effective_store = WorkflowEffectiveStateStore(
            self.workflow_store,
            self.revision_store,
            self.activation_store,
        )

        for target in ("dispatched", "running", "succeeded"):
            self.workflow_store.set_node_state(WORKFLOW_ID, "audit", target)
        resolution = self.workflow_store.resolve_planner_checkpoint(
            WORKFLOW_ID,
            "review-audit",
            resolver="chatgpt-planner",
        )
        self.first = revision_one(self.base)
        self.revision_store.append(WORKFLOW_ID, self.first)
        base_states = dict(self.workflow_store.load_state(WORKFLOW_ID)["node_states"])
        self.activation_store.append(
            WORKFLOW_ID,
            1,
            base_states,
            resolution,
            activated_at="2026-09-19T16:02:00Z",
        )
        self.effective_store.initialize(WORKFLOW_ID)

        self.control = GitWorkflowControlPlane(
            origin_url_for=lambda _repository: self.origin.as_uri()
        )
        self.cancellation = GitWorkflowCancellationTransport(self.control)

    def cycle(self):
        return run_lineage_cycle(
            self.effective_store,
            WORKFLOW_ID,
            [self.repository],
            self.control,
            self.cancellation,
        )

    def sync_seed(self) -> None:
        run_git(self.seed, "pull", "--rebase", "origin", "agent-control")

    def test_running_child_cancel_request_requires_terminal_result_before_graph_cancel(self) -> None:
        first_cycle = self.cycle()
        self.assertEqual(first_cycle.execution.published, ("implement",))
        child = publishing.materialize_lineage_child_task(
            self.base,
            [self.first],
            "implement",
        )
        digest = task_digest(child)

        self.sync_seed()
        publish_from_seed(
            self.seed,
            ".agent/status/daemon.json",
            {
                "state": "running",
                "current_task_id": child["id"],
                "current_task_digest": digest,
            },
            "Mark workflow child running",
        )
        running_cycle = self.cycle()
        self.assertEqual(running_cycle.execution.reconciled, ("implement",))
        self.assertEqual(running_cycle.cancellation.requested, ())
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["node_states"]["implement"],
            "running",
        )

        cancelled = self.effective_store.cancel(WORKFLOW_ID)
        self.assertTrue(cancelled["cancel_requested"])
        self.assertEqual(cancelled["node_states"]["implement"], "running")

        requested = self.cycle()
        self.assertEqual(requested.execution.published, ())
        self.assertEqual(requested.cancellation.requested, ("implement",))
        request = remote_json(
            self.origin,
            "agent-control",
            ".agent/daemon/control.json",
        )
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request["action"], "cancel_task")
        self.assertEqual(request["task_id"], child["id"])
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["node_states"]["implement"],
            "running",
        )

        self.sync_seed()
        publish_from_seed(
            self.seed,
            f".agent/daemon/acks/{request['id']}.json",
            {
                "id": request["id"],
                "action": "cancel_task",
                "status": "accepted",
                "task_id": child["id"],
                "result": "terminating_active_task",
            },
            "Accept workflow child cancellation",
        )
        acknowledged = self.cycle()
        self.assertEqual(acknowledged.cancellation.accepted, ("implement",))
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["node_states"]["implement"],
            "running",
        )

        self.sync_seed()
        publish_from_seed(
            self.seed,
            f".agent/results/{child['id']}.json",
            {
                "id": child["id"],
                "status": "failed",
                "failure_reason": "cancelled_by_operator",
                "task_digest": digest,
            },
            "Publish terminal workflow child cancellation",
        )
        terminal = self.cycle()
        self.assertEqual(terminal.execution.reconciled, ("implement",))
        self.assertEqual(terminal.cancellation.requested, ())
        self.assertEqual(terminal.cancellation.accepted, ())
        final = self.effective_store.load(WORKFLOW_ID)
        self.assertEqual(final["node_states"]["implement"], "cancelled")
        self.assertEqual(final["node_states"]["review-implementation"], "cancelled")
        self.assertEqual(final["workflow_state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
