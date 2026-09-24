from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from local_agent.conversation import bootstrap, contract

MANUAL_ATTACH_SCHEMA_VERSION = 1
MAX_MANUAL_ATTACH_INTENT_BYTES = 16 * 1024

_INTENT_FIELDS = frozenset(
    {
        "schema_version",
        "child_request_id",
        "child_request_digest",
        "workflow_id",
        "workflow_node_id",
        "workflow_node_revision",
        "workflow_node_introduction_digest",
        "parent_conversation_url",
        "child_conversation_url",
        "repository_id",
        "agent_binding",
        "bootstrap_contract_version",
        "bootstrap_digest",
    }
)


def _canonical_bytes(payload: Any) -> bytes:
    try:
        text = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("manual attach intent must be canonical JSON data") from exc
    return text.encode("utf-8")


def _require_exact(value: Any, expected: Any, *, field: str) -> None:
    if isinstance(value, str) and isinstance(expected, str):
        if secrets.compare_digest(value, expected):
            return
    elif value == expected:
        return
    raise ValueError(f"manual attach {field} does not match admitted request")


def validate_manual_attach_intent(
    intent: dict[str, Any],
    *,
    request: dict[str, Any],
) -> None:
    if not isinstance(intent, dict):
        raise ValueError("manual attach intent must be an object")
    contract.validate_child_request(request)
    if len(_canonical_bytes(intent)) > MAX_MANUAL_ATTACH_INTENT_BYTES:
        raise ValueError(
            f"manual attach intent exceeds {MAX_MANUAL_ATTACH_INTENT_BYTES} bytes"
        )
    extra = set(intent) - _INTENT_FIELDS
    if extra:
        raise ValueError(
            f"manual attach intent contains unsupported fields: {sorted(extra)!r}"
        )
    missing = _INTENT_FIELDS - set(intent)
    if missing:
        raise ValueError(
            f"manual attach intent is missing required fields: {sorted(missing)!r}"
        )
    if (
        type(intent.get("schema_version")) is not int
        or intent["schema_version"] != MANUAL_ATTACH_SCHEMA_VERSION
    ):
        raise ValueError(
            f"manual attach schema_version must be {MANUAL_ATTACH_SCHEMA_VERSION}"
        )

    expected = {
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "workflow_id": request["workflow_id"],
        "workflow_node_id": request["workflow_node_id"],
        "workflow_node_revision": request["workflow_node_revision"],
        "workflow_node_introduction_digest": request[
            "workflow_node_introduction_digest"
        ],
        "parent_conversation_url": request["parent_conversation_url"],
        "repository_id": request["repository_id"],
        "agent_binding": request["agent_binding"],
        "bootstrap_contract_version": request["bootstrap_contract_version"],
    }
    for field, value in expected.items():
        _require_exact(intent.get(field), value, field=field)

    child_url = contract.canonical_conversation_url(
        intent.get("child_conversation_url")
    )
    if intent["child_conversation_url"] != child_url:
        raise ValueError(
            "manual attach child_conversation_url must use canonical ChatGPT form"
        )
    if child_url == request["parent_conversation_url"]:
        raise ValueError("manual attach child conversation must differ from parent")

    bootstrap.require_child_bootstrap_digest(
        request,
        expected_digest=intent.get("bootstrap_digest"),
    )


def build_manual_attach_intent(
    request: dict[str, Any],
    *,
    child_conversation_url: str,
    submitted_bootstrap_digest: str,
) -> dict[str, Any]:
    contract.validate_child_request(request)
    bootstrap.require_child_bootstrap_digest(
        request,
        expected_digest=submitted_bootstrap_digest,
    )
    child_url = contract.canonical_conversation_url(child_conversation_url)
    if child_url == request["parent_conversation_url"]:
        raise ValueError("manual attach child conversation must differ from parent")

    intent = {
        "schema_version": MANUAL_ATTACH_SCHEMA_VERSION,
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "workflow_id": request["workflow_id"],
        "workflow_node_id": request["workflow_node_id"],
        "workflow_node_revision": request["workflow_node_revision"],
        "workflow_node_introduction_digest": request[
            "workflow_node_introduction_digest"
        ],
        "parent_conversation_url": request["parent_conversation_url"],
        "child_conversation_url": child_url,
        "repository_id": request["repository_id"],
        "agent_binding": request["agent_binding"],
        "bootstrap_contract_version": request["bootstrap_contract_version"],
        "bootstrap_digest": submitted_bootstrap_digest,
    }
    validate_manual_attach_intent(intent, request=request)
    return intent


def manual_attach_digest(
    intent: dict[str, Any],
    *,
    request: dict[str, Any],
) -> str:
    validate_manual_attach_intent(intent, request=request)
    return "sha256:" + hashlib.sha256(_canonical_bytes(intent)).hexdigest()


def reconcile_manual_attach_intent(
    existing: dict[str, Any] | None,
    candidate: dict[str, Any],
    *,
    request: dict[str, Any],
) -> dict[str, Any]:
    validate_manual_attach_intent(candidate, request=request)
    if existing is None:
        return dict(candidate)
    validate_manual_attach_intent(existing, request=request)
    if not secrets.compare_digest(
        manual_attach_digest(existing, request=request),
        manual_attach_digest(candidate, request=request),
    ):
        raise ValueError("conflicting manual attach intent")
    return dict(existing)


def registration_from_manual_attach(
    intent: dict[str, Any],
    *,
    request: dict[str, Any],
    registered_at: str,
) -> dict[str, Any]:
    validate_manual_attach_intent(intent, request=request)
    registration = {
        "schema_version": contract.CHILD_REGISTRATION_SCHEMA_VERSION,
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "parent_conversation_url": request["parent_conversation_url"],
        "child_conversation_url": intent["child_conversation_url"],
        "registered_at": registered_at,
    }
    contract.validate_child_registration(registration, request=request)
    return registration
