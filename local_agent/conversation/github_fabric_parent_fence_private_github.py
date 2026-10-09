"""Default-disabled private GitHub writer for a global synthetic parent fence.

No real prompt, browser Send, live child ACK, DOM authority or implicit token.
An immutable synthetic record and its global index are committed atomically.
Every ambiguous ref outcome is reconciled from a fresh commit-pinned snapshot.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from local_agent.conversation import github_fabric_github as git
from local_agent.conversation import github_fabric_parent_fence_preview as preview
from local_agent.conversation import github_fabric_private_github as private

MAX_ATTEMPTS = 6
MAX_TREE_ITEMS = 4096
_PARENT_FILE = re.compile(r"parents/parent-[0-9a-f]{32}\.json\Z")


@dataclass(frozen=True, slots=True)
class PrivateParentFenceReceipt:
    status: str
    head_sha: str
    parent_id: str


def _snapshot(api: Any, candidate_id: str) -> tuple[
    str, str, dict[str, Any] | None, dict[str, dict[str, Any] | None]
]:
    ref = api.request("GET", private.REF_PATH)
    if (ref.get("ref") != "refs/heads/" + private.PRIVATE_BRANCH
            or ref.get("object", {}).get("type") != "commit"):
        raise ValueError("Parent fence origin ref invalid")
    head = git._require_sha(ref.get("object", {}).get("sha"), label="parent fence head")
    commit = api.request("GET", f"/git/commits/{head}")
    tree_sha = git._require_sha(
        commit.get("tree", {}).get("sha"), label="parent fence tree"
    )
    listing = api.request("GET", f"/git/trees/{tree_sha}?recursive=1")
    entries = listing.get("tree")
    if (listing.get("sha") != tree_sha or listing.get("truncated") is not False
            or not isinstance(entries, list) or len(entries) > MAX_TREE_ITEMS):
        raise ValueError("Parent fence origin tree incomplete")
    record_paths: set[str] = set()
    index_present = False
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("Parent fence tree entry invalid")
        path = entry["path"]
        if path == "parents":
            if entry.get("type") != "tree":
                raise ValueError("Parent fence root is not a directory")
            continue
        if not path.startswith("parents/"):
            continue
        if entry.get("type") != "blob" or entry.get("mode") != "100644":
            raise ValueError("Parent fence unexpected tree entry")
        if path == preview.INDEX_PATH:
            if index_present:
                raise ValueError("Parent fence duplicate index")
            index_present = True
        elif _PARENT_FILE.fullmatch(path):
            if path in record_paths:
                raise ValueError("Parent fence duplicate record")
            record_paths.add(path)
        else:
            raise ValueError("Parent fence unexpected path")

    index = git._read_json_at_commit(
        api, preview.INDEX_PATH, head, max_bytes=preview.MAX_INDEX_BYTES
    )
    if index_present != (index is not None):
        raise ValueError("Parent fence index/tree mismatch")
    parent_ids = preview.validate_index(index)["parent_ids"]
    if record_paths != {preview.parent_path(identifier) for identifier in parent_ids}:
        raise ValueError("Parent fence origin has orphan or dangling paths")
    records: dict[str, dict[str, Any] | None] = {}
    for identifier in (*parent_ids, candidate_id):
        if identifier in records:
            continue
        records[identifier] = git._read_json_at_commit(
            api, preview.parent_path(identifier), head,
            max_bytes=preview.MAX_RECORD_BYTES,
        )
    return head, tree_sha, index, records


def _commit_atomic(api: Any, head: str, tree_sha: str,
                   plan: preview.ParentTransportPreviewPlan,
                   candidate_id: str) -> None:
    if (plan.operation != "commit_atomic" or plan.expected_head_sha != head
            or len(plan.writes) != 2
            or tuple(path for path, _ in plan.writes) != (
                preview.parent_path(candidate_id), preview.INDEX_PATH
            )):
        raise ValueError("Parent fence CAS plan is stale or invalid")
    entries = []
    for path, payload in plan.writes:
        data = preview._encoded(payload) + b"\n"
        limit = preview.MAX_INDEX_BYTES if path == preview.INDEX_PATH else preview.MAX_RECORD_BYTES
        if len(data) > limit:
            raise ValueError("Parent fence data exceeds bound")
        blob = api.request("POST", "/git/blobs", {
            "content": data.decode("utf-8"), "encoding": "utf-8",
        })
        entries.append({
            "path": path, "mode": "100644", "type": "blob",
            "sha": git._require_sha(blob.get("sha"), label="parent fence blob"),
        })
    new_tree = api.request("POST", "/git/trees", {
        "base_tree": tree_sha, "tree": entries,
    })
    new_tree_sha = git._require_sha(new_tree.get("sha"), label="parent fence new tree")
    new_commit = api.request("POST", "/git/commits", {
        "message": "Synthetic private parent fence atomic preview",
        "tree": new_tree_sha, "parents": [head],
    })
    commit_sha = git._require_sha(new_commit.get("sha"), label="parent fence commit")
    api.request("PATCH", private.REF_UPDATE_PATH, {
        "sha": commit_sha, "force": False,
    })


def publish_private_parent_fence_synthetic(
    operator_request: dict[str, Any], child_requests: list[dict[str, Any]],
    *, transport_mode: str, enabled: bool = False,
    token: str | None = None, api: Any | None = None,
) -> PrivateParentFenceReceipt:
    """Opt-in trusted adapter; fixture must match exact public synthetic bytes.

    This never retries a browser effect. A lost GitHub write acknowledgment only
    triggers a pinned remote re-read before another CAS can be considered.
    """
    if enabled is not True:
        raise PermissionError("Private parent fence writer is default-disabled")
    candidate = preview.build_preview(
        operator_request, child_requests, transport_mode=transport_mode
    )
    if api is None:
        api = private.PrivateFabricREST(token)
    attempted = False
    for _ in range(MAX_ATTEMPTS):
        head, tree_sha, index, records = _snapshot(api, candidate["id"])
        plan = preview.preflight_parent_transport_preview(
            operator_request, child_requests, transport_mode=transport_mode,
            existing_index=index, existing_records=records,
            expected_head_sha=head, enabled=True, writer_authorized=True,
        )
        if plan.operation == "replay":
            return PrivateParentFenceReceipt(
                "converged" if attempted else "replay", head, candidate["id"]
            )
        attempted = True
        try:
            _commit_atomic(api, head, tree_sha, plan, candidate["id"])
        except git.GithubFabricHTTPError as exc:
            if exc.status not in {409, 422}:
                raise
        except git.GithubFabricTransportError:
            pass
        # Even a successful PATCH is not terminal evidence until a new
        # complete, pinned snapshot proves the record and index agree.
    raise RuntimeError("Private parent fence CAS did not converge")
