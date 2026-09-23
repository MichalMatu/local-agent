from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.workflow import coordinator, publishing
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.git_cancellation import (
    CancelRequestEvidence,
    CancelRequestState,
)
from local_agent.workflow.lineage_cycle import run_lineage_cycle
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore
from tests.test_workflow_lineage_cancellation import (
    WORKFLOW_ID,
    MemoryControlPlane,
    base_manifest,
    repository,
    revision_one,
)


class MemoryCancellationTransport:
    def __init__(self, state: CancelRequestState = CancelRequestState.REQUESTED) -> None:
        self.state = state
        self.calls: list[tuple[str, str, str]] = []

    def request_cancel(self, repository, task_id, expected_task_digest):
        self.calls.append((repository.repository_id, task_id, expected_task_digest))
        return CancelRequestEvidence(
            state=self.state,
            control_id="wf-cancel-cycle",
            task_id=task_id,
        )


class WorkflowLineageCycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
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
        self.repo = repository(self.root)
        self.control = MemoryControlPlane()

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
            activated_at="2026-09-19T16:10:00Z",
        )
        self.effective_store.initialize(WORKFLOW_ID)
        self.cancellation = MemoryCancellationTransport()

    def cycle(self):
        return run_lineage_cycle(
            self.effective_store,
            WORKFLOW_ID,
            [self.repo],
            self.control,
            self.cancellation,
        )

    def test_normal_cycle_dispatches_without_cancellation_transport(self) -> None:
        result = self.cycle()

        self.assertEqual(result.execution.published, ("implement",))
        self.assertEqual(result.cancellation.requested, ())
        self.assertEqual(self.cancellation.calls, [])

    def test_cancel_before_cycle_prevents_dispatch_and_needs_no_remote_cancel(self) -> None:
        self.effective_store.cancel(WORKFLOW_ID)

        result = self.cycle()

        self.assertEqual(result.execution.published, ())
        self.assertEqual(result.cancellation.requested, ())
        self.assertEqual(self.control.publish_calls, [])
        self.assertEqual(self.cancellation.calls, [])
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["workflow_state"],
            "cancelled",
        )

    def test_running_child_after_cancel_is_reconciled_then_cancel_requested(self) -> None:
        first = self.cycle()
        self.assertEqual(first.execution.published, ("implement",))
        child = publishing.materialize_lineage_child_task(
            self.base,
            [self.first],
            "implement",
        )
        key = (self.repo.repository_id, str(child["id"]))
        self.control.kinds[key] = coordinator.ChildEvidenceKind.RUNNING
        self.effective_store.cancel(WORKFLOW_ID)

        result = self.cycle()

        self.assertEqual(result.execution.reconciled, ("implement",))
        self.assertEqual(result.cancellation.requested, ("implement",))
        self.assertEqual(len(self.cancellation.calls), 1)
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["node_states"]["implement"],
            "running",
        )

    def test_terminal_cancel_evidence_finishes_graph_before_cancel_phase(self) -> None:
        self.cycle()
        child = publishing.materialize_lineage_child_task(
            self.base,
            [self.first],
            "implement",
        )
        key = (self.repo.repository_id, str(child["id"]))
        self.control.kinds[key] = coordinator.ChildEvidenceKind.RUNNING
        self.cycle()
        self.effective_store.cancel(WORKFLOW_ID)
        self.control.kinds[key] = coordinator.ChildEvidenceKind.CANCELLED

        result = self.cycle()

        self.assertEqual(result.execution.reconciled, ("implement",))
        self.assertEqual(result.cancellation.requested, ())
        self.assertEqual(self.cancellation.calls, [])
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["workflow_state"],
            "cancelled",
        )

    def test_deferred_cancellation_is_visible_without_state_invention(self) -> None:
        self.cycle()
        child = publishing.materialize_lineage_child_task(
            self.base,
            [self.first],
            "implement",
        )
        key = (self.repo.repository_id, str(child["id"]))
        self.control.kinds[key] = coordinator.ChildEvidenceKind.RUNNING
        self.cycle()
        self.effective_store.cancel(WORKFLOW_ID)
        self.cancellation.state = CancelRequestState.DEFERRED
        self.cancellation.calls.clear()

        result = self.cycle()

        self.assertEqual(result.cancellation.deferred, ("implement",))
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["node_states"]["implement"],
            "running",
        )


if __name__ == "__main__":
    unittest.main()
