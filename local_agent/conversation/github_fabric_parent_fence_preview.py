"""Default-disabled parent transport arbitration *preview*, not an authority.

A fixture-restricted admission model for a future single parent-mode fence.
No browser/DOM driver participates in this lock yet. No record returned by
this module permits child Send, private prompt publication or machine work.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from local_agent.conversation import contract
from local_agent.conversation import github_fabric_dispatch
from local_agent.conversation import github_fabric_publication as synthetic

SCHEMA_VERSION = 1
ROOT = "parents/"
INDEX_PATH = ROOT + "index.json"
MAX_PARENTS = 16
MAX_INDEX_BYTES = 4096
MAX_RECORD_BYTES = 4096
KIND = "synthetic_parent_transport_arbitration_preview"
PHASE = "unattested_no_browser_authority"
ACK_STATE = "not_attested"
MODES = frozenset({"legacy_dom", "github_first"})
_PROJECT = "local-agent"
_ID_RE = re.compile(r"parent-[0-9a-f]{32}\Z")
_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REQ_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\Z")
_FIELDS = frozenset({
    "schema_version", "kind", "id", "project_id",
    "parent_conversation_url", "workflow_id", "operator_request_id",
    "operator_request_digest", "dispatch_id", "transport_mode",
    "fence_epoch", "phase", "browser_send_authorized", "ack_state",
})


def _encoded(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ValueError("Parent transport preview requires canonical JSON") from exc


def parent_id(parent_conversation_url: str) -> str:
    canonical = contract.canonical_conversation_url(parent_conversation_url)
    if canonical != parent_conversation_url:
        raise ValueError("Parent transport URL must be canonical")
    identity = _encoded(["fabric-global-parent-mode-v1", canonical])
    return "parent-" + hashlib.sha256(identity).hexdigest()[:32]


def parent_path(identifier: str) -> str:
    if not isinstance(identifier, str) or not _ID_RE.fullmatch(identifier):
        raise ValueError("Parent transport preview path identity invalid")
    return ROOT + identifier + ".json"


def validate_index(value: Any) -> dict[str, Any]:
    if value is None:
        return {"schema_version": SCHEMA_VERSION, "parent_ids": []}
    if not isinstance(value, dict) or set(value) != {"schema_version", "parent_ids"}:
        raise ValueError("Parent transport index fields invalid")
    ids = value["parent_ids"]
    if (type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION
            or not isinstance(ids, list) or len(ids) > MAX_PARENTS
            or any(not isinstance(x, str) or not _ID_RE.fullmatch(x) for x in ids)
            or ids != sorted(set(ids)) or len(_encoded(value)) > MAX_INDEX_BYTES):
        raise ValueError("Parent transport index invalid")
    return {"schema_version": SCHEMA_VERSION, "parent_ids": list(ids)}


def validate_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("Parent transport preview record fields invalid")
    try:
        identity = parent_id(value["parent_conversation_url"])
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Parent transport preview parent identity invalid") from exc
    if (type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION
            or value["kind"] != KIND
            or value["id"] != identity
            or value["project_id"] != _PROJECT
            or not isinstance(value["transport_mode"], str)
            or value["transport_mode"] not in MODES
            or type(value["fence_epoch"]) is not int or value["fence_epoch"] != 1
            or value["phase"] != PHASE
            or value["browser_send_authorized"] is not False
            or value["ack_state"] != ACK_STATE
            or not isinstance(value["operator_request_digest"], str)
            or not _DIGEST_RE.fullmatch(value["operator_request_digest"])
            or not isinstance(value["dispatch_id"], str)
            or not re.fullmatch(r"fabric-[0-9a-f]{32}", value["dispatch_id"])
            or any(not isinstance(value[field], str) or not _REQ_RE.fullmatch(value[field])
                   for field in ("workflow_id", "operator_request_id"))
            or len(_encoded(value)) > MAX_RECORD_BYTES):
        raise ValueError("Parent transport preview record invalid")
    return value


def build_preview(operator_request: dict[str, Any],
                  child_requests: Iterable[dict[str, Any]],
                  *, transport_mode: str) -> dict[str, Any]:
    if transport_mode not in MODES:
        raise ValueError("Parent transport mode invalid")
    requests = list(child_requests)
    # Fixed SHA-256 of the *entire* known-public fixture; a caller-provided
    # project/fixture marker cannot declassify user content.
    synthetic.preflight_synthetic_publication(
        operator_request, requests,
        existing_record=None, existing_index=None,
        expected_head_sha="0" * 40,
        enabled=True, writer_authorized=True,
    )
    dispatch = github_fabric_dispatch.build_github_fabric_dispatch(
        operator_request, requests
    )
    candidate = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "id": parent_id(dispatch["parent_conversation_url"]),
        "project_id": _PROJECT,
        "parent_conversation_url": dispatch["parent_conversation_url"],
        "workflow_id": operator_request["workflow_id"],
        "operator_request_id": dispatch["request_id"],
        "operator_request_digest": dispatch["request_digest"],
        "dispatch_id": dispatch["id"],
        "transport_mode": transport_mode,
        "fence_epoch": 1,
        "phase": PHASE,
        "browser_send_authorized": False,
        "ack_state": ACK_STATE,
    }
    validate_record(candidate)
    return candidate


@dataclass(frozen=True, slots=True)
class ParentTransportPreviewPlan:
    operation: str
    expected_head_sha: str
    writes: tuple[tuple[str, dict[str, Any]], ...]


def preflight_parent_transport_preview(
    operator_request: dict[str, Any],
    child_requests: Iterable[dict[str, Any]],
    *,
    transport_mode: str,
    existing_index: dict[str, Any] | None,
    existing_records: Mapping[str, dict[str, Any] | None],
    expected_head_sha: str,
    enabled: bool = False,
    writer_authorized: bool = False,
) -> ParentTransportPreviewPlan:
    if enabled is not True or writer_authorized is not True:
        raise PermissionError("Parent transport preview is default-disabled")
    if not isinstance(expected_head_sha, str) or not _SHA_RE.fullmatch(expected_head_sha):
        raise ValueError("Parent transport preview requires exact origin SHA")
    candidate = build_preview(
        operator_request, child_requests, transport_mode=transport_mode
    )
    index = validate_index(existing_index)
    records = dict(existing_records)
    required = set(index["parent_ids"]) | {candidate["id"]}
    if set(records) != required:
        raise ValueError("Parent transport origin snapshot incomplete")
    for identifier, record in records.items():
        parent_path(identifier)
        if record is not None:
            validate_record(record)
            if record["id"] != identifier:
                raise ValueError("Parent transport preview record/path conflict")
        if identifier in index["parent_ids"] and record is None:
            raise ValueError("Parent transport index has dangling record")
        if identifier not in index["parent_ids"] and record is not None:
            raise ValueError("Parent transport preview record not indexed")

    prior = records[candidate["id"]]
    if prior is not None:
        if not hmac.compare_digest(_encoded(prior), _encoded(candidate)):
            raise ValueError("Parent transport mode/identity already occupied")
        return ParentTransportPreviewPlan("replay", expected_head_sha, ())
    identifiers = sorted(set(index["parent_ids"]) | {candidate["id"]})
    next_index = validate_index({
        "schema_version": SCHEMA_VERSION, "parent_ids": identifiers
    })
    return ParentTransportPreviewPlan(
        "commit_atomic", expected_head_sha,
        ((parent_path(candidate["id"]), candidate), (INDEX_PATH, next_index)),
    )
