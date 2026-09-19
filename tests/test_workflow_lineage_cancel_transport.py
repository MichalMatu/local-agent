from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import coordinator, lineage_coordinator, publishing
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.git_cancellation import (
    CancelRequestEvidence,
    CancelRequestState,
)
from local_agent.workflow.lineage_cancellation import request_lineage_cancellations
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
    def __init__(self, state: CancelRequestState) -> None:
        self.state = state
        self.calls: list[tuple[str, str, str]] = []

    def request_cancel(self, repository, task_id, expected_task_digest):
        self.calls.append(
            (repository.repository_id, task_id, expected_task_digest)
        )
        return CancelRequestEvidence(
            state=self.state,
            control_id="wf-cancel-test",
            task_id=task_id,
        )


class InvalidCancellationTransport:
    def request_cancel(self, repository, task_id, expected_task_digest):
        return {"state": "requested", "task_id": task_id}


class WorkflowLineageCancelTransportTests(unittest.TestCase):
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
            activated_at="2026-09-19T15:40:00Z",
        )
        self.effective_store.initialize(WORKFLOW_ID)

    def tick(self) -> coordinator.TickResult:
        return lineage_coordinator.tick_lineage_workflow(
            self.effective_store,
            WORKFLOW_ID,
            [self.repo],
            self.control,
        )

    def make_running(self) -> dict:
        self.assertEqual(self.tick().published, ("implement",))
        child = publishing.materialize_lineage_child_task(
            self.base,
            [self.first],
            "implement",
        )
        key = (self.repo.repository_id, str(child["id"]))
        self.control.kinds[key] = coordinator.ChildEvidenceKind.RUNNING
        self.tick()
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["node_states"]["implement"],
            "running",
        )
        return child

    def test_cancel_tick_requests_exact_active_child_without_mutating_node_state(self) -> None:
        child = self.make_running()
        self.effective_store.cancel(WORKFLOW_ID)
        transport = MemoryCancellationTransport(CancelRequestState.REQUESTED)

        result = request_lineage_cancellations(
            self.effective_store,
            WORKFLOW_ID,
            [self.repo],
            transport,
        )

        self.assertEqual(result.requested, ("implement",))
        self.assertEqual(
            transport.calls,
            [
                (
                    self.repo.repository_id,
                    str(child["id"]),
                    task_digest(child),
                )
            ],
        )
        current = self.effective_store.load(WORKFLOW_ID)
        self.assertEqual(current["node_states"]["implement"], "running")
        self.assertEqual(current["node_states"]["review-implementation"], "cancelled")

    def test_busy_control_slot_is_reported_as_deferred_and_is_retryable(self) -> None:
        self.make_running()
        self.effective_store.cancel(WORKFLOW_ID)
        transport = MemoryCancellationTransport(CancelRequestState.DEFERRED)

        first = request_lineage_cancellations(
            self.effective_store,
            WORKFLOW_ID,
            [self.repo],
            transport,
        )
        second = request_lineage_cancellations(
            self.effective_store,
            WORKFLOW_ID,
            [self.repo],
            transport,
        )

        self.assertEqual(first.deferred, ("implement",))
        self.assertEqual(second.deferred, ("implement",))
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["node_states"]["implement"],
            "running",
        )

    def test_no_cancel_request_means_no_transport_call(self) -> None:
        self.make_running()
        transport = MemoryCancellationTransport(CancelRequestState.REQUESTED)

        result = request_lineage_cancellations(
            self.effective_store,
            WORKFLOW_ID,
            [self.repo],
            transport,
        )

        self.assertEqual(result.requested, ())
        self.assertEqual(transport.calls, [])

    def test_terminal_child_is_not_cancel_requested_after_reconciliation(self) -> None:
        child = self.make_running()
        self.effective_store.cancel(WORKFLOW_ID)
        key = (self.repo.repository_id, str(child["id"]))
        self.control.kinds[key] = coordinator.ChildEvidenceKind.CANCELLED
        self.tick()
        transport = MemoryCancellationTransport(CancelRequestState.REQUESTED)

        result = request_lineage_cancellations(
            self.effective_store,
            WORKFLOW_ID,
            [self.repo],
            transport,
        )

        self.assertEqual(result.requested, ())
        self.assertEqual(transport.calls, [])
        self.assertEqual(
            self.effective_store.load(WORKFLOW_ID)["workflow_state"],
            "cancelled",
        )

    def test_invalid_transport_evidence_fails_closed(self) -> None:
        self.make_running()
        self.effective_store.cancel(WORKFLOW_ID)

        with self.assertRaisesRegex(
            coordinator.WorkflowIntegrityError,
            "cancellation transport returned invalid evidence",
        ):
            request_lineage_cancellations(
                self.effective_store,
                WORKFLOW_ID,
                [self.repo],
                InvalidCancellationTransport(),
            )


if __name__ == "__main__":
    unittest.main()
