from __future__ import annotations

from dataclasses import dataclass

from local_agent.repository.context import RepositoryContext
from local_agent.workflow.coordinator import TickResult, WorkflowControlPlane
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.lineage_cancellation import (
    CancellationTickResult,
    WorkflowCancellationTransport,
    request_lineage_cancellations,
)
from local_agent.workflow.lineage_coordinator import tick_lineage_workflow


@dataclass(frozen=True, slots=True)
class LineageCycleResult:
    execution: TickResult
    cancellation: CancellationTickResult


def run_lineage_cycle(
    store: WorkflowEffectiveStateStore,
    workflow_id: str,
    repositories: list[RepositoryContext],
    control_plane: WorkflowControlPlane,
    cancellation_transport: WorkflowCancellationTransport,
) -> LineageCycleResult:
    """Run one unwired effective-lineage reconciliation/dispatch/cancellation cycle.

    The two phases deliberately acquire the workflow execution lock independently.
    `tick_lineage_workflow` always reconciles exact child evidence before considering
    dispatch. If cancellation was requested before that tick, it publishes no new child.
    If cancellation becomes visible after an earlier dispatch, the second phase requests
    cancellation only for the exact active child. ACK evidence never mutates task state;
    a later execution tick must observe exact terminal result evidence.

    This façade is intentionally not imported by daemon/supervisor/worker code.
    """
    execution = tick_lineage_workflow(
        store,
        workflow_id,
        repositories,
        control_plane,
    )
    cancellation = request_lineage_cancellations(
        store,
        workflow_id,
        repositories,
        cancellation_transport,
    )
    return LineageCycleResult(
        execution=execution,
        cancellation=cancellation,
    )
