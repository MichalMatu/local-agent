"""Trusted staging of real private Fabric dispatches, without browser authority.

A successful record/index commit is durable GitHub intake data, NOT an ACK,
a parent transport lease, or permission for Chat Bridge to press Send.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from local_agent.conversation import github_fabric_dispatch as dispatch_contract
from local_agent.conversation import github_fabric_github as git
from local_agent.conversation import github_fabric_private_github as private_git
from local_agent.conversation import github_fabric_private_publication as catalog

MAX_ATTEMPTS = 4
PROJECT_ID = "local-agent"
WORKFLOW_ID = "workflow-001"


@dataclass(frozen=True, slots=True)
class PrivateDispatchPublication:
    status: str
    source_head_sha: str
    dispatch_id: str
    completed_commits: int


def _snapshot(api: Any, record_path: str) -> tuple[
    str, str, dict[str, Any] | None, dict[str, Any] | None,
    dict[str, Any] | None, dict[str, Any] | None
]:
    ref = api.request("GET", private_git.REF_PATH)
    if (ref.get("ref") != "refs/heads/" + private_git.PRIVATE_BRANCH
            or ref.get("object", {}).get("type") != "commit"):
        raise ValueError("Private Fabric live origin ref invalid")
    head = git._require_sha(ref.get("object", {}).get("sha"), label="private origin head")
    commit = api.request("GET", f"/git/commits/{head}")
    tree = git._require_sha(commit.get("tree", {}).get("sha"), label="private origin tree")
    values = [
        git._read_json_at_commit(api, path, head, max_bytes=limit)
        for path, limit in (
            (catalog.CATALOG_PATH, catalog.MAX_INDEX_BYTES),
            (catalog.WORKFLOWS_PATH, catalog.MAX_INDEX_BYTES),
            (catalog.INDEX_PATH, catalog.MAX_INDEX_BYTES),
            (record_path, catalog.MAX_RECORD_BYTES),
        )
    ]
    return head, tree, *values


def _validate_remote(
    projects: dict[str, Any] | None,
    workflows: dict[str, Any] | None,
    index: dict[str, Any] | None,
    record: dict[str, Any] | None,
    dispatch: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    if (projects is None or PROJECT_ID not in catalog.validate_projects(projects)
            or workflows is None
            or WORKFLOW_ID not in catalog.validate_workflows(workflows)):
        raise PermissionError("Private Fabric live project/workflow not indexed")
    ids = [] if index is None else catalog.validate_dispatch_index(index)
    identifier = dispatch["id"]
    if identifier in ids:
        if record is None:
            raise ValueError("Private Fabric indexed dispatch record missing")
        dispatch_contract.reconcile_github_fabric_dispatch(record, dispatch)
        return "replay", None
    if record is not None:
        raise ValueError("Private Fabric unindexed dispatch requires manual recovery")
    if len(ids) >= catalog.MAX_DISPATCH_IDS:
        raise ValueError("Private Fabric dispatch index at capacity")
    updated = {"schema_version": 1, "dispatch_ids": sorted([*ids, identifier])}
    catalog.validate_dispatch_index(updated)
    return "commit_atomic", updated


def _commit_atomic(
    api: Any, *, head: str, tree: str, dispatch: dict[str, Any],
    index: dict[str, Any],
) -> None:
    entries = []
    for path, payload, maximum in (
        (catalog.dispatch_path(dispatch["id"]), dispatch, catalog.MAX_RECORD_BYTES),
        (catalog.INDEX_PATH, index, catalog.MAX_INDEX_BYTES),
    ):
        data = dispatch_contract._canonical_bytes(payload) + b"\n"
        if len(data) > maximum:
            raise ValueError("Private Fabric live dispatch payload oversized")
        blob = api.request("POST", "/git/blobs", {
            "content": data.decode("utf-8"), "encoding": "utf-8"
        })
        entries.append({
            "path": path, "mode": "100644", "type": "blob",
            "sha": git._require_sha(blob.get("sha"), label="private live blob"),
        })
    new_tree = api.request("POST", "/git/trees", {
        "base_tree": tree, "tree": entries,
    })
    sha = git._require_sha(new_tree.get("sha"), label="private live tree")
    commit = api.request("POST", "/git/commits", {
        "message": "Stage private Fabric dispatch (no browser authority)",
        "tree": sha, "parents": [head],
    })
    new_head = git._require_sha(commit.get("sha"), label="private live commit")
    api.request("PATCH", private_git.REF_UPDATE_PATH, {
        "sha": new_head, "force": False,
    })


def stage_private_dispatch(
    operator_request: dict[str, Any],
    child_requests: list[dict[str, Any]],
    *,
    enabled: bool = False,
    writer_authorized: bool = False,
    token: str | None = None,
    api: Any | None = None,
) -> PrivateDispatchPublication:
    """Stage only an already validated, explicitly approved workflow in private GitHub.

    This function intentionally does not change a parent transport mode or
    schedule any browser effect. Failed/ambiguous GitHub writes are always
    followed by fresh immutable reads before another CAS attempt.
    """
    if enabled is not True or writer_authorized is not True:
        raise PermissionError("Private Fabric live staging is disabled")
    dispatch = dispatch_contract.build_github_fabric_dispatch(
        operator_request, child_requests
    )
    if operator_request["workflow_id"] != WORKFLOW_ID:
        raise PermissionError("Private Fabric live workflow is not approved")
    if api is None:
        api = private_git.PrivateFabricREST(token)
    record_path = catalog.dispatch_path(dispatch["id"])
    attempted = False
    commits = 0
    for _ in range(MAX_ATTEMPTS):
        head, tree, projects, workflows, index, record = _snapshot(api, record_path)
        operation, updated = _validate_remote(
            projects, workflows, index, record, dispatch
        )
        if operation == "replay":
            return PrivateDispatchPublication(
                "converged" if attempted else "replay", head, dispatch["id"], commits
            )
        if updated is None:
            raise AssertionError("Private Fabric live index update missing")
        try:
            attempted = True
            _commit_atomic(api, head=head, tree=tree, dispatch=dispatch, index=updated)
            commits += 1
        except git.GithubFabricHTTPError as exc:
            if exc.status not in {409, 422}:
                raise
        except git.GithubFabricTransportError:
            # A lost PATCH response does not imply failure. Re-read before retry.
            continue
    raise RuntimeError("Private Fabric live staging did not converge")
