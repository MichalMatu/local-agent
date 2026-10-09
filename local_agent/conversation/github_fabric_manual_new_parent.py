"""Read-only manual new-parent preview from a recovered *synthetic* dispatch.

This does not authenticate the supplied source or operate a browser, Local
Agent, or GitHub. In particular it cannot retire an old/offline DOM worker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from local_agent.conversation import contract

_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,200}\Z")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_PRIVATE = "private_synthetic_dispatch_unattested"
_PUBLIC = "public_synthetic_observation_only"
_BASE = frozenset({
    "source_kind", "source_head_sha", "parent_conversation_url",
    "workflow_id", "operator_request_id", "dispatch_id", "children",
})


@dataclass(frozen=True, slots=True)
class ManualNewParentPreview:
    source_parent_conversation_url: str
    destination_parent_conversation_url: str
    source_head_sha: str
    source_kind: str
    workflow_id: str
    dispatch_id: str
    child_request_ids: tuple[str, ...]
    decision: str = "manual_read_only_review"
    browser_effects_permitted: bool = False
    automatic_retry_permitted: bool = False
    legacy_worker_retirement_proven: bool = False


def _id(value: Any) -> bool:
    return isinstance(value, str) and _ID_RE.fullmatch(value) is not None


def _canonical_url(value: Any) -> str:
    canonical = contract.canonical_conversation_url(value)
    if canonical != value:
        raise ValueError("Manual new-parent preview requires canonical conversation URLs")
    return canonical


def preview_manual_new_parent(
    observation: Mapping[str, Any], *,
    independently_pinned_source_sha: str,
    destination_parent_conversation_url: str,
) -> ManualNewParentPreview:
    """Validate a redacted, recovered fixture DTO for operator-only review.

    Pass dataclasses.asdict(recovered) from the verified public/private
    synthetic recovery reader. An independent trusted source SHA is required
    from the operator: this function checks equality, NOT Git provenance.
    No returned field authorizes automated execution or browser effects.
    """
    if not isinstance(observation, dict):
        raise ValueError("Manual new-parent observation must be a strict mapping")
    kind = observation.get("source_kind")
    if kind == _PRIVATE:
        expected = _BASE | {"project_id"}
        child_fields = frozenset({
            "request_id", "spawn_transaction_id", "child_request_digest",
            "bootstrap_digest", "execution_state",
        })
        state_field = "execution_state"
        child_id_field = "request_id"
    elif kind == _PUBLIC:
        expected = _BASE | {"schema_version"}
        child_fields = frozenset({
            "claim_id", "workflow_node_id", "child_request_id",
            "spawn_transaction_id", "lifecycle",
        })
        state_field = "lifecycle"
        child_id_field = "child_request_id"
    else:
        raise ValueError("Manual new-parent source kind is unsupported")

    if (set(observation) != expected or
            (kind == _PRIVATE and observation["project_id"] != "local-agent") or
            (kind == _PUBLIC and
             (type(observation["schema_version"]) is not int or
              observation["schema_version"] != 1))):
        raise ValueError("Manual new-parent observation envelope invalid")
    head = observation["source_head_sha"]
    if (not isinstance(head, str) or _SHA_RE.fullmatch(head) is None or
            not isinstance(independently_pinned_source_sha, str) or
            _SHA_RE.fullmatch(independently_pinned_source_sha) is None or
            head != independently_pinned_source_sha):
        raise ValueError("Manual new-parent source SHA must match independent pin")

    source = _canonical_url(observation["parent_conversation_url"])
    destination = _canonical_url(destination_parent_conversation_url)
    if source == destination:
        raise ValueError("Manual rehydration must use a different parent conversation")
    if not _id(observation["workflow_id"]) or not _id(observation["operator_request_id"]) or not _id(observation["dispatch_id"]):
        raise ValueError("Manual new-parent workflow identities invalid")

    children = observation["children"]
    # Both existing recovery DTOs are exactly the approved two-child fixture.
    if not isinstance(children, (list, tuple)) or len(children) != 2:
        raise ValueError("Manual new-parent synthetic child count invalid")
    ids: list[str] = []
    for child in children:
        if not isinstance(child, dict) or set(child) != child_fields:
            raise ValueError("Manual new-parent child identity shape invalid")
        if child[state_field] != "published_execution_unconfirmed":
            raise ValueError("Manual new-parent child state cannot prove an effect")
        if any(not _id(child[field]) for field in child_fields - {
            state_field, "child_request_digest", "bootstrap_digest"
        }):
            raise ValueError("Manual new-parent child identifiers invalid")
        if kind == _PRIVATE and any(
            not isinstance(child[field], str) or _DIGEST_RE.fullmatch(child[field]) is None
            for field in ("child_request_digest", "bootstrap_digest")
        ):
            raise ValueError("Manual new-parent child digests invalid")
        ids.append(child[child_id_field])
    if len(set(ids)) != len(ids):
        raise ValueError("Manual new-parent duplicate child request identity")

    return ManualNewParentPreview(
        source_parent_conversation_url=source,
        destination_parent_conversation_url=destination,
        source_head_sha=head,
        source_kind=kind,
        workflow_id=observation["workflow_id"],
        dispatch_id=observation["dispatch_id"],
        child_request_ids=tuple(ids),
    )
