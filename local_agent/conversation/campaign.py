from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from local_agent.conversation import contract, records, state
from local_agent.conversation.record_store import WorkflowConversationRecordLedger
from local_agent.conversation.store import WorkflowConversationStore, now_iso

CAMPAIGN_LEDGER_SCHEMA_VERSION = 1
MAX_LEDGER_SUMMARY_CHARS = 1024
MAX_PARENT_LEDGER_BYTES = 512 * 1024
MAX_SELECTED_CONTEXT_RECORDS = 16
MAX_SELECTED_CONTEXT_BYTES = 128 * 1024
CHILD_TERMINAL_CONTEXT_KIND = "child_terminal"


@dataclass(frozen=True, slots=True)
class ReasoningReconcileResult:
    recovered_child_states: tuple[str, ...] = ()
    reconciled_workflow_nodes: tuple[str, ...] = ()


def _canonical_bytes(payload: Any) -> bytes:
    try:
        text = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("campaign projection must contain canonical JSON data") from exc
    return text.encode("utf-8")


def _parse_timestamp(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{field} must use UTC")
    return parsed


def _bounded_summary(summary: str) -> tuple[str, bool]:
    if len(summary) <= MAX_LEDGER_SUMMARY_CHARS:
        return summary, False
    return summary[:MAX_LEDGER_SUMMARY_CHARS], True


def _requests_by_node(
    conversation_store: WorkflowConversationStore,
) -> dict[str, dict[str, Any]]:
    by_node: dict[str, dict[str, Any]] = {}
    for request_id in conversation_store.request_ids():
        request = conversation_store.load_request(request_id)
        node_id = str(request["workflow_node_id"])
        existing = by_node.get(node_id)
        if existing is not None and existing["id"] != request["id"]:
            raise ValueError(
                f"workflow reasoning node {node_id!r} has multiple durable child requests: "
                f"{existing['id']!r} and {request['id']!r}"
            )
        by_node[node_id] = request
    return by_node


def _terminal_record_ref(
    request: dict[str, Any],
    terminal: dict[str, Any],
) -> dict[str, str]:
    return {
        "kind": CHILD_TERMINAL_CONTEXT_KIND,
        "id": str(request["id"]),
        "digest": records.child_terminal_digest(terminal, request=request),
    }


def reconcile_reasoning_children(
    conversation_store: WorkflowConversationStore,
    record_ledger: WorkflowConversationRecordLedger | None = None,
) -> ReasoningReconcileResult:
    """Repair durable reasoning-child/workflow state after restart.

    Durable child records are authoritative only for reasoning-child lifecycle. Workflow
    success/failure is advanced from an exact durable terminal record, never from browser
    state or a model assertion. The existing WorkflowStore remains graph authority.
    """
    if not isinstance(conversation_store, WorkflowConversationStore):
        raise TypeError("conversation_store must be a WorkflowConversationStore")
    ledger = record_ledger or WorkflowConversationRecordLedger(conversation_store)
    if ledger.store is not conversation_store:
        raise ValueError("record_ledger must belong to conversation_store")

    recovered_child_states: list[str] = []
    reconciled_workflow_nodes: list[str] = []

    with conversation_store._mutation_lock():
        requests = _requests_by_node(conversation_store)
        workflow = conversation_store.workflow_store.load_state(
            conversation_store.workflow_id
        )

        for node_id, request in requests.items():
            lifecycle = conversation_store.load_state(str(request["id"]))
            terminal = ledger.load_terminal(str(request["id"]))
            workflow_node_state = workflow["node_states"].get(node_id)
            if workflow_node_state is None:
                raise ValueError(
                    f"reasoning child node {node_id!r} is absent from authoritative workflow state"
                )

            if terminal is None:
                if lifecycle["state"] in {"terminal_recorded", "retired"}:
                    raise ValueError(
                        f"child {request['id']!r} is {lifecycle['state']} without a durable terminal"
                    )
                if workflow_node_state in {"succeeded", "failed"}:
                    raise ValueError(
                        f"workflow reasoning node {node_id!r} is {workflow_node_state} "
                        "without a durable child terminal"
                    )
                continue

            if lifecycle["state"] == "terminal_pending_evidence":
                updated = dict(lifecycle)
                updated["state"] = state.transition_child_state(
                    lifecycle["state"],
                    "terminal_recorded",
                )
                updated["updated_at"] = now_iso()
                conversation_store._write_state(str(request["id"]), updated)
                lifecycle = updated
                recovered_child_states.append(str(request["id"]))
            elif lifecycle["state"] not in {"terminal_recorded", "retired"}:
                raise ValueError(
                    f"durable terminal conflicts with child lifecycle state "
                    f"{lifecycle['state']!r} for {request['id']!r}"
                )

            target = "succeeded" if terminal["outcome"] == "succeeded" else "failed"
            if workflow_node_state == target:
                continue
            if workflow_node_state != "waiting_conversation":
                raise ValueError(
                    f"durable child terminal for {node_id!r} conflicts with workflow "
                    f"node state {workflow_node_state!r}"
                )
            workflow = conversation_store.workflow_store.set_node_state(
                conversation_store.workflow_id,
                node_id,
                target,
            )
            reconciled_workflow_nodes.append(node_id)

    return ReasoningReconcileResult(
        recovered_child_states=tuple(recovered_child_states),
        reconciled_workflow_nodes=tuple(reconciled_workflow_nodes),
    )


def project_parent_ledger(
    conversation_store: WorkflowConversationStore,
    record_ledger: WorkflowConversationRecordLedger | None = None,
) -> dict[str, Any]:
    """Build a compact read-only parent projection without transcript content."""
    if not isinstance(conversation_store, WorkflowConversationStore):
        raise TypeError("conversation_store must be a WorkflowConversationStore")
    ledger = record_ledger or WorkflowConversationRecordLedger(conversation_store)
    if ledger.store is not conversation_store:
        raise ValueError("record_ledger must belong to conversation_store")

    with conversation_store._mutation_lock():
        manifest = conversation_store.workflow_store.load_manifest(
            conversation_store.workflow_id
        )
        workflow = conversation_store.workflow_store.load_state(
            conversation_store.workflow_id
        )
        requests = _requests_by_node(conversation_store)
        children: list[dict[str, Any]] = []

        node_order = {
            str(node["id"]): index for index, node in enumerate(manifest["nodes"])
        }
        ordered_requests = sorted(
            requests.values(),
            key=lambda request: (
                node_order.get(str(request["workflow_node_id"]), len(node_order)),
                str(request["id"]),
            ),
        )

        for request in ordered_requests:
            request_id = str(request["id"])
            lifecycle = conversation_store.load_state(request_id)
            registration = conversation_store.load_registration(request_id)
            checkpoints = ledger.load_checkpoints(request_id)
            terminal = ledger.load_terminal(request_id)

            latest_checkpoint: dict[str, Any] | None = None
            if checkpoints:
                latest = checkpoints[-1]
                summary, truncated = _bounded_summary(str(latest["summary"]))
                latest_checkpoint = {
                    "sequence": latest["sequence"],
                    "summary": summary,
                    "summary_truncated": truncated,
                    "digest": records.child_checkpoint_digest(
                        latest,
                        request=request,
                    ),
                }

            terminal_projection: dict[str, Any] | None = None
            if terminal is not None:
                summary, truncated = _bounded_summary(str(terminal["summary"]))
                terminal_projection = {
                    "outcome": terminal["outcome"],
                    "summary": summary,
                    "summary_truncated": truncated,
                    "evidence_ref_count": len(terminal["evidence_refs"]),
                    "evidence_refs": [dict(reference) for reference in terminal["evidence_refs"]],
                    "record_ref": _terminal_record_ref(request, terminal),
                }

            children.append(
                {
                    "workflow_node_id": request["workflow_node_id"],
                    "workflow_node_revision": request["workflow_node_revision"],
                    "workflow_node_introduction_digest": request[
                        "workflow_node_introduction_digest"
                    ],
                    "child_request_id": request_id,
                    "child_request_digest": contract.child_request_digest(request),
                    "role": request["role"],
                    "repository_id": request["repository_id"],
                    "lifecycle_state": lifecycle["state"],
                    "child_conversation_url": (
                        registration["child_conversation_url"]
                        if registration is not None
                        else None
                    ),
                    "latest_checkpoint": latest_checkpoint,
                    "terminal": terminal_projection,
                }
            )

        projection = {
            "schema_version": CAMPAIGN_LEDGER_SCHEMA_VERSION,
            "workflow_id": conversation_store.workflow_id,
            "manifest_digest": workflow["manifest_digest"],
            "workflow_state": workflow["workflow_state"],
            "node_states": dict(workflow["node_states"]),
            "reasoning_children": children,
        }
        if len(_canonical_bytes(projection)) > MAX_PARENT_LEDGER_BYTES:
            raise ValueError(
                f"parent campaign ledger exceeds {MAX_PARENT_LEDGER_BYTES} bytes"
            )
        return projection


def select_child_terminal_context(
    conversation_store: WorkflowConversationStore,
    request_id: str,
    record_ledger: WorkflowConversationRecordLedger | None = None,
) -> list[dict[str, Any]]:
    """Resolve only explicitly referenced durable child-terminal context.

    Other context kinds remain available for their own future resolvers and are ignored
    here. A matching `child_terminal` reference is accepted only if the durable record is
    terminal, same-workflow, digest-exact and not from the future relative to the target
    request creation timestamp.
    """
    if not isinstance(conversation_store, WorkflowConversationStore):
        raise TypeError("conversation_store must be a WorkflowConversationStore")
    ledger = record_ledger or WorkflowConversationRecordLedger(conversation_store)
    if ledger.store is not conversation_store:
        raise ValueError("record_ledger must belong to conversation_store")

    with conversation_store._mutation_lock():
        target = conversation_store.load_request(request_id)
        refs = [
            reference
            for reference in target["context_refs"]
            if reference["kind"] == CHILD_TERMINAL_CONTEXT_KIND
        ]
        if len(refs) > MAX_SELECTED_CONTEXT_RECORDS:
            raise ValueError(
                "selected child-terminal context exceeds "
                f"{MAX_SELECTED_CONTEXT_RECORDS} records"
            )

        selected: list[dict[str, Any]] = []
        target_created_at = _parse_timestamp(
            str(target["created_at"]),
            field="target child request created_at",
        )
        for reference in refs:
            source_id = str(reference["id"])
            if source_id == target["id"]:
                raise ValueError("child request cannot select its own terminal as context")
            source = conversation_store.load_request(source_id)
            terminal = ledger.load_terminal(source_id)
            if terminal is None:
                raise ValueError(
                    f"selected child terminal is unavailable: {source_id!r}"
                )
            source_state = conversation_store.load_state(source_id)
            if source_state["state"] not in {"terminal_recorded", "retired"}:
                raise ValueError(
                    f"selected child terminal {source_id!r} is not durably terminal"
                )

            actual_digest = records.child_terminal_digest(terminal, request=source)
            if reference["digest"] != actual_digest:
                raise ValueError(
                    f"selected child terminal digest mismatch for {source_id!r}"
                )
            terminal_recorded_at = _parse_timestamp(
                str(terminal["recorded_at"]),
                field="selected child terminal recorded_at",
            )
            if terminal_recorded_at > target_created_at:
                raise ValueError(
                    f"selected child terminal {source_id!r} was recorded after target request creation"
                )

            selected.append(
                {
                    "kind": CHILD_TERMINAL_CONTEXT_KIND,
                    "id": source_id,
                    "digest": actual_digest,
                    "workflow_node_id": terminal["workflow_node_id"],
                    "outcome": terminal["outcome"],
                    "summary": terminal["summary"],
                    "evidence_refs": terminal["evidence_refs"],
                }
            )

        if len(_canonical_bytes(selected)) > MAX_SELECTED_CONTEXT_BYTES:
            raise ValueError(
                f"selected child-terminal context exceeds {MAX_SELECTED_CONTEXT_BYTES} bytes"
            )
        return selected
