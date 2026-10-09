"""Portable, offline-only synthetic parent handoff with independent Git recheck.

A manifest is a human-carried review object, never an execution permit.
Its SHA-256 digest protects accidental corruption, not against tampering.
Only an independently pinned, matching GitHub recovery can authenticate
its claimed *synthetic* source. Neither path can retire browser workers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from local_agent.conversation import github_fabric_manual_new_parent as manual

MANIFEST_SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 4096

_PAYLOAD_FIELDS = frozenset({
    "schema_version", "source_kind", "source_head_sha",
    "source_parent_conversation_url", "destination_parent_conversation_url",
    "workflow_id", "dispatch_id", "child_request_ids", "decision",
    "browser_effects_permitted", "automatic_retry_permitted",
    "legacy_worker_retirement_proven",
})
_MANIFEST_FIELDS = _PAYLOAD_FIELDS | {"manifest_digest"}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _validate_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _PAYLOAD_FIELDS:
        raise ValueError("Manual handoff payload fields invalid")
    if type(value["schema_version"]) is not int or value["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise ValueError("Manual handoff schema invalid")
    if value["source_kind"] not in (manual._PRIVATE, manual._PUBLIC):
        raise ValueError("Manual handoff source kind invalid")
    if not isinstance(value["source_head_sha"], str) or manual._SHA_RE.fullmatch(value["source_head_sha"]) is None:
        raise ValueError("Manual handoff source commit SHA invalid")
    source = manual._canonical_url(value["source_parent_conversation_url"])
    destination = manual._canonical_url(value["destination_parent_conversation_url"])
    if source == destination:
        raise ValueError("Manual handoff requires a separate destination parent")
    if not manual._id(value["workflow_id"]):
        raise ValueError("Manual handoff workflow identity invalid")
    if not isinstance(value["dispatch_id"], str) or manual._DISPATCH_RE.fullmatch(value["dispatch_id"]) is None:
        raise ValueError("Manual handoff dispatch identity invalid")
    ids = value["child_request_ids"]
    if (
        type(ids) is not list or len(ids) != 2
        or any(not manual._id(identifier) for identifier in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("Manual handoff children identities invalid")
    if value["decision"] != "manual_read_only_review":
        raise ValueError("Manual handoff cannot authorize a different decision")
    if any(value[key] is not False for key in (
        "browser_effects_permitted", "automatic_retry_permitted",
        "legacy_worker_retirement_proven",
    )):
        raise ValueError("Manual handoff cannot grant execution, retry or retirement")
    if len(_canonical_bytes(value)) > MAX_MANIFEST_BYTES:
        raise ValueError("Manual handoff payload too large")
    return value


def _digest(payload: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def export_manual_handoff(preview: manual.ManualNewParentPreview) -> str:
    """Return canonical, bounded JSON to be reviewed/copied manually.

    This routine never calls GitHub, ChatGPT, an agent or a browser.
    """
    if type(preview) is not manual.ManualNewParentPreview:
        raise ValueError("Manual handoff requires a validated preview DTO")
    payload = {
        **asdict(preview),
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "child_request_ids": list(preview.child_request_ids),
    }
    _validate_payload(payload)
    manifest = {**payload, "manifest_digest": _digest(payload)}
    encoded = _canonical_bytes(manifest)
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError("Manual handoff manifest too large")
    return encoded.decode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Manual handoff JSON has duplicate keys")
        value[key] = item
    return value


def import_manual_handoff(
    manifest: str, *,
    independently_pinned_source_sha: str,
    expected_destination_parent_conversation_url: str,
) -> manual.ManualNewParentPreview:
    """Parse hand-carried review data without treating its digest as provenance."""
    if type(manifest) is not str or len(manifest.encode("utf-8")) > MAX_MANIFEST_BYTES:
        raise ValueError("Manual handoff input must be bounded UTF-8 JSON text")
    try:
        value = json.loads(manifest, object_pairs_hook=_reject_duplicate_keys)
    except (TypeError, json.JSONDecodeError, UnicodeEncodeError) as exc:
        raise ValueError("Manual handoff JSON invalid") from exc
    if not isinstance(value, dict) or set(value) != _MANIFEST_FIELDS:
        raise ValueError("Manual handoff manifest fields invalid")
    payload = {key: value[key] for key in _PAYLOAD_FIELDS}
    _validate_payload(payload)
    if manifest != _canonical_bytes(value).decode("utf-8"):
        raise ValueError("Manual handoff must use canonical JSON")
    if not isinstance(value["manifest_digest"], str) or value["manifest_digest"] != _digest(payload):
        raise ValueError("Manual handoff digest mismatch (integrity only)")
    head = value["source_head_sha"]
    if (
        not isinstance(independently_pinned_source_sha, str)
        or manual._SHA_RE.fullmatch(independently_pinned_source_sha) is None
        or head != independently_pinned_source_sha
    ):
        raise ValueError("Manual handoff source SHA does not match independent pin")
    if manual._canonical_url(expected_destination_parent_conversation_url) != value[
        "destination_parent_conversation_url"
    ]:
        raise ValueError("Manual handoff destination parent mismatch")

    return manual.ManualNewParentPreview(
        source_parent_conversation_url=value["source_parent_conversation_url"],
        destination_parent_conversation_url=value["destination_parent_conversation_url"],
        source_head_sha=head,
        source_kind=value["source_kind"],
        workflow_id=value["workflow_id"],
        dispatch_id=value["dispatch_id"],
        child_request_ids=tuple(value["child_request_ids"]),
    )


def verify_manual_handoff_against_github(
    manifest: str,
    operator_request: dict[str, Any],
    child_requests: list[dict[str, Any]],
    *,
    independently_pinned_source_sha: str,
    expected_destination_parent_conversation_url: str,
    enabled: bool = False,
    token: str | None = None,
    api: Any | None = None,
) -> manual.ManualNewParentPreview:
    """Require a fresh read-only recovered Git origin to match the hand-carried DTO.

    The operator remains responsible for independently establishing the source
    pin and ensuring that the destination has no legacy automation attached.
    """
    if enabled is not True:
        raise PermissionError("Manual handoff remote verification is default-disabled")
    carried = import_manual_handoff(
        manifest,
        independently_pinned_source_sha=independently_pinned_source_sha,
        expected_destination_parent_conversation_url=expected_destination_parent_conversation_url,
    )
    recovered = manual.preview_manual_new_parent_from_github(
        operator_request, child_requests,
        source_kind=carried.source_kind,
        independently_pinned_source_sha=independently_pinned_source_sha,
        destination_parent_conversation_url=carried.destination_parent_conversation_url,
        enabled=True, token=token, api=api,
    )
    if recovered != carried:
        raise ValueError("Manual handoff does not match GitHub recovered source")
    return recovered
