from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from local_agent.runtime.task_contract import task_digest


class ChildEvidenceKind(Enum):
    ABSENT = "absent"
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    DIGEST_MISMATCH = "digest_mismatch"


@dataclass(frozen=True, slots=True)
class ChildEvidence:
    kind: ChildEvidenceKind
    task_digest: str | None = None
    failure_reason: str | None = None


_NO_REPLAY_FAILURES = frozenset(
    {
        "interrupted_previous_attempt",
        "corrupt_claim_state",
    }
)


def _digest_mismatch(actual_digest: str | None) -> ChildEvidence:
    return ChildEvidence(
        ChildEvidenceKind.DIGEST_MISMATCH,
        task_digest=actual_digest,
    )


def classify_child_evidence(
    *,
    task_payload: dict[str, Any] | None,
    status_payload: dict[str, Any] | None,
    result_payload: dict[str, Any] | None,
    expected_task_id: str,
    expected_digest: str,
) -> ChildEvidence:
    """Classify exact repository evidence without performing any I/O.

    Result evidence wins over live status. Exact running status can prove an active child
    even if a freshly synchronized task snapshot is temporarily unavailable. Every
    available digest is checked before it can advance workflow state.
    """
    if not isinstance(expected_task_id, str) or not expected_task_id:
        raise ValueError("expected_task_id must be a non-empty string")
    if not isinstance(expected_digest, str) or not expected_digest:
        raise ValueError("expected_digest must be a non-empty string")

    if result_payload is not None:
        if not isinstance(result_payload, dict):
            raise ValueError("result_payload must be an object or None")
        if result_payload.get("id") != expected_task_id:
            return _digest_mismatch(
                str(result_payload.get("task_digest"))
                if result_payload.get("task_digest") is not None
                else None
            )
        actual_digest = result_payload.get("task_digest")
        if actual_digest != expected_digest:
            return _digest_mismatch(
                str(actual_digest) if actual_digest is not None else None
            )
        failure_reason = result_payload.get("failure_reason")
        reason = failure_reason if isinstance(failure_reason, str) else None
        if result_payload.get("status") == "done":
            return ChildEvidence(
                ChildEvidenceKind.SUCCEEDED,
                task_digest=expected_digest,
            )
        if reason == "cancelled_by_operator":
            return ChildEvidence(
                ChildEvidenceKind.CANCELLED,
                task_digest=expected_digest,
                failure_reason=reason,
            )
        if reason in _NO_REPLAY_FAILURES:
            return ChildEvidence(
                ChildEvidenceKind.INTERRUPTED,
                task_digest=expected_digest,
                failure_reason=reason,
            )
        return ChildEvidence(
            ChildEvidenceKind.FAILED,
            task_digest=expected_digest,
            failure_reason=reason,
        )

    status = status_payload if isinstance(status_payload, dict) else {}
    if status.get("current_task_id") == expected_task_id:
        current_digest = status.get("current_task_digest")
        if current_digest != expected_digest:
            return _digest_mismatch(
                str(current_digest) if current_digest is not None else None
            )
        return ChildEvidence(
            ChildEvidenceKind.RUNNING,
            task_digest=expected_digest,
        )

    if task_payload is None:
        return ChildEvidence(ChildEvidenceKind.ABSENT)
    if not isinstance(task_payload, dict):
        raise ValueError("task_payload must be an object or None")
    if task_payload.get("id") != expected_task_id:
        try:
            actual_digest = task_digest(task_payload)
        except Exception:
            actual_digest = None
        return _digest_mismatch(actual_digest)

    try:
        actual_digest = task_digest(task_payload)
    except Exception:
        return _digest_mismatch(None)
    if actual_digest != expected_digest:
        return _digest_mismatch(actual_digest)

    return ChildEvidence(
        ChildEvidenceKind.PENDING,
        task_digest=expected_digest,
    )


def _has_exact_terminal_result(
    task_id: str,
    result_payloads: dict[str, dict[str, Any]],
) -> bool:
    result = result_payloads.get(task_id)
    return (
        isinstance(result, dict)
        and result.get("id") == task_id
        and result.get("status") in {"done", "failed"}
    )


def has_unrelated_work(
    *,
    child_task_id: str,
    status_payload: dict[str, Any] | None,
    task_payloads: list[dict[str, Any]],
    result_payloads: dict[str, dict[str, Any]],
) -> bool:
    """Return whether unrelated repository work should make workflow dispatch yield."""
    if not isinstance(child_task_id, str) or not child_task_id:
        raise ValueError("child_task_id must be a non-empty string")
    if not isinstance(task_payloads, list):
        raise ValueError("task_payloads must be a list")
    if not isinstance(result_payloads, dict):
        raise ValueError("result_payloads must be an object")

    status = status_payload if isinstance(status_payload, dict) else {}
    for field in ("current_task_id", "pending_task_id"):
        task_id = status.get(field)
        if isinstance(task_id, str) and task_id and task_id != child_task_id:
            return True

    for payload in task_payloads:
        if not isinstance(payload, dict):
            raise ValueError("task_payloads items must be objects")
        task_id = payload.get("id")
        if not isinstance(task_id, str) or not task_id or task_id == child_task_id:
            continue
        if not _has_exact_terminal_result(task_id, result_payloads):
            return True
    return False
