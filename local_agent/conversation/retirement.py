from __future__ import annotations

import secrets
from typing import Any

from local_agent.conversation import contract, records, state
from local_agent.conversation.record_store import WorkflowConversationRecordLedger
from local_agent.conversation.store import WorkflowConversationStore, now_iso

RETIREMENT_AUTHORITY_SCHEMA_VERSION = 1
RETIREMENT_RECEIPT_SCHEMA_VERSION = 1
RETIREMENT_RESULTS = frozenset({"closed", "already_closed"})

_AUTHORITY_FIELDS = frozenset(
    {
        "schema_version",
        "child_request_id",
        "child_request_digest",
        "child_conversation_url",
        "terminal_digest",
    }
)
_RECEIPT_FIELDS = frozenset({*_AUTHORITY_FIELDS, "result"})


def _require_exact(actual: Any, expected: Any, *, field: str) -> None:
    if isinstance(actual, str) and isinstance(expected, str):
        if secrets.compare_digest(actual, expected):
            return
    elif actual == expected:
        return
    raise ValueError(f"retirement {field} does not match durable authority")


def build_retirement_authority(
    request: dict[str, Any],
    registration: dict[str, Any],
    terminal: dict[str, Any],
) -> dict[str, Any]:
    contract.validate_child_request(request)
    contract.validate_child_registration(registration, request=request)
    records.validate_child_terminal(terminal, request=request)
    return {
        "schema_version": RETIREMENT_AUTHORITY_SCHEMA_VERSION,
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "child_conversation_url": registration["child_conversation_url"],
        "terminal_digest": records.child_terminal_digest(terminal, request=request),
    }


def validate_retirement_authority(
    authority: dict[str, Any],
    *,
    request: dict[str, Any],
    registration: dict[str, Any],
    terminal: dict[str, Any],
) -> None:
    if not isinstance(authority, dict) or set(authority) != _AUTHORITY_FIELDS:
        raise ValueError("retirement authority fields do not match schema")
    if authority.get("schema_version") != RETIREMENT_AUTHORITY_SCHEMA_VERSION:
        raise ValueError(
            f"retirement authority schema_version must be {RETIREMENT_AUTHORITY_SCHEMA_VERSION}"
        )
    expected = build_retirement_authority(request, registration, terminal)
    for field in _AUTHORITY_FIELDS:
        _require_exact(authority.get(field), expected[field], field=field)


def build_retirement_receipt(
    authority: dict[str, Any],
    *,
    result: str,
) -> dict[str, Any]:
    if result not in RETIREMENT_RESULTS:
        raise ValueError(f"retirement result must be one of {sorted(RETIREMENT_RESULTS)!r}")
    if not isinstance(authority, dict) or set(authority) != _AUTHORITY_FIELDS:
        raise ValueError("retirement authority fields do not match schema")
    receipt = dict(authority)
    receipt["schema_version"] = RETIREMENT_RECEIPT_SCHEMA_VERSION
    receipt["result"] = result
    return receipt


def validate_retirement_receipt(
    receipt: dict[str, Any],
    *,
    authority: dict[str, Any],
) -> None:
    if not isinstance(receipt, dict) or set(receipt) != _RECEIPT_FIELDS:
        raise ValueError("retirement receipt fields do not match schema")
    if receipt.get("schema_version") != RETIREMENT_RECEIPT_SCHEMA_VERSION:
        raise ValueError(
            f"retirement receipt schema_version must be {RETIREMENT_RECEIPT_SCHEMA_VERSION}"
        )
    result = receipt.get("result")
    if result not in RETIREMENT_RESULTS:
        raise ValueError(f"retirement result must be one of {sorted(RETIREMENT_RESULTS)!r}")
    for field in _AUTHORITY_FIELDS - {"schema_version"}:
        _require_exact(receipt.get(field), authority.get(field), field=field)


class WorkflowConversationRetirement:
    """Issue exact close authority only after durable terminal evidence exists."""

    def __init__(
        self,
        store: WorkflowConversationStore,
        ledger: WorkflowConversationRecordLedger,
    ) -> None:
        if not isinstance(store, WorkflowConversationStore):
            raise TypeError("store must be a WorkflowConversationStore")
        if not isinstance(ledger, WorkflowConversationRecordLedger) or ledger.store is not store:
            raise TypeError("ledger must belong to the same WorkflowConversationStore")
        self.store = store
        self.ledger = ledger

    def issue_close_authority(self, request_id: str) -> dict[str, Any]:
        with self.store._mutation_lock():
            request = self.store.load_request(request_id)
            registration = self.store.load_registration(request_id)
            if registration is None:
                raise ValueError("child retirement requires a durable registration")
            terminal = self.ledger.load_terminal(request_id)
            if terminal is None:
                raise ValueError("child retirement requires a durable terminal record")
            lifecycle = self.store.load_state(request_id)
            if lifecycle["state"] != "terminal_recorded":
                raise ValueError("child close authority requires terminal_recorded state")
            return build_retirement_authority(request, registration, terminal)

    def confirm_closed(
        self,
        request_id: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        with self.store._mutation_lock():
            request = self.store.load_request(request_id)
            registration = self.store.load_registration(request_id)
            if registration is None:
                raise ValueError("child retirement requires a durable registration")
            terminal = self.ledger.load_terminal(request_id)
            if terminal is None:
                raise ValueError("child retirement requires a durable terminal record")
            authority = build_retirement_authority(request, registration, terminal)
            validate_retirement_receipt(receipt, authority=authority)

            lifecycle = self.store.load_state(request_id)
            if lifecycle["state"] == "retired":
                return lifecycle
            if lifecycle["state"] != "terminal_recorded":
                raise ValueError("child retirement confirmation requires terminal_recorded state")
            updated = dict(lifecycle)
            updated["state"] = state.transition_child_state(
                lifecycle["state"],
                "retired",
            )
            updated["updated_at"] = now_iso()
            self.store._write_state(request_id, updated)
            return updated
