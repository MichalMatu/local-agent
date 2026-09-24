from __future__ import annotations

import json
import secrets
from typing import Any

from local_agent.conversation import bootstrap, contract

BRIDGE_ADOPTION_SCHEMA_VERSION = 1
MAX_BRIDGE_ADOPTION_AUTHORITY_BYTES = 4096

_AUTHORITY_FIELDS = frozenset(
    {
        "schema_version",
        "child_request_id",
        "child_request_digest",
        "child_conversation_url",
        "repository_id",
        "agent_binding",
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
        raise ValueError("bridge adoption authority must be canonical JSON data") from exc
    return text.encode("utf-8")


def _require_exact(value: Any, expected: Any, *, field: str) -> None:
    if isinstance(value, str) and isinstance(expected, str):
        if secrets.compare_digest(value, expected):
            return
    elif value == expected:
        return
    raise ValueError(f"bridge adoption {field} does not match durable authority")


def validate_bridge_adoption_authority(
    authority: dict[str, Any],
    *,
    request: dict[str, Any],
    registration: dict[str, Any],
) -> None:
    if not isinstance(authority, dict):
        raise ValueError("bridge adoption authority must be an object")
    contract.validate_child_request(request)
    contract.validate_child_registration(registration, request=request)
    if len(_canonical_bytes(authority)) > MAX_BRIDGE_ADOPTION_AUTHORITY_BYTES:
        raise ValueError(
            "bridge adoption authority exceeds "
            f"{MAX_BRIDGE_ADOPTION_AUTHORITY_BYTES} bytes"
        )
    extra = set(authority) - _AUTHORITY_FIELDS
    if extra:
        raise ValueError(
            f"bridge adoption authority contains unsupported fields: {sorted(extra)!r}"
        )
    missing = _AUTHORITY_FIELDS - set(authority)
    if missing:
        raise ValueError(
            f"bridge adoption authority is missing required fields: {sorted(missing)!r}"
        )
    if (
        type(authority.get("schema_version")) is not int
        or authority["schema_version"] != BRIDGE_ADOPTION_SCHEMA_VERSION
    ):
        raise ValueError(
            "bridge adoption schema_version must be "
            f"{BRIDGE_ADOPTION_SCHEMA_VERSION}"
        )

    expected = {
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "child_conversation_url": registration["child_conversation_url"],
        "repository_id": request["repository_id"],
        "agent_binding": request["agent_binding"],
    }
    for field, value in expected.items():
        _require_exact(authority.get(field), value, field=field)

    bootstrap.require_child_bootstrap_digest(
        request,
        expected_digest=authority.get("bootstrap_digest"),
    )


def build_bridge_adoption_authority(
    request: dict[str, Any],
    registration: dict[str, Any],
    *,
    bootstrap_digest: str,
) -> dict[str, Any]:
    contract.validate_child_request(request)
    contract.validate_child_registration(registration, request=request)
    bootstrap.require_child_bootstrap_digest(
        request,
        expected_digest=bootstrap_digest,
    )
    authority = {
        "schema_version": BRIDGE_ADOPTION_SCHEMA_VERSION,
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "child_conversation_url": registration["child_conversation_url"],
        "repository_id": request["repository_id"],
        "agent_binding": request["agent_binding"],
        "bootstrap_digest": bootstrap_digest,
    }
    validate_bridge_adoption_authority(
        authority,
        request=request,
        registration=registration,
    )
    return authority
