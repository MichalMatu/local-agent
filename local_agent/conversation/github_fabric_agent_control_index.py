"""Bounded GitHub-first task-result discovery without Chat Bridge.

This discovers only task IDs under an explicitly supplied prefix from one
pinned agent-control Git tree, then reuses the GET-only result reconciliation.
It never dispatches, retries, rebinds or mutates any task/worker state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from local_agent.conversation import github_fabric_agent_control_recovery as receipt
from local_agent.conversation import github_fabric_github as git

MAX_GIT_TREE_ENTRIES = 2048
MAX_SCOPED_TASKS = 16
_ID_PREFIX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{7,119}\Z")
_TASK_ROOT = ".agent/tasks/"
_RESULT_ROOT = ".agent/results/"


@dataclass(frozen=True, slots=True)
class AgentControlReadOnlyHistory:
    control_commit_sha: str
    source_commit_sha: str
    expected_work_branch: str
    selected_task_prefix: str
    result_observations: tuple[receipt.AgentControlReadOnlyObservation, ...]
    unconfirmed_task_ids: tuple[str, ...]
    decision: str = "operator_review_only"
    can_dispatch: bool = False
    can_retry: bool = False
    can_authorize_browser_effect: bool = False


def discover_agent_control_results(
    *,
    task_id_prefix: str,
    independently_pinned_control_sha: str,
    independently_pinned_source_sha: str,
    expected_agent_binding: str,
    expected_work_branch: str,
    enabled: bool = False,
    token: str | None = None,
    api: Any | None = None,
) -> AgentControlReadOnlyHistory:
    """Return bounded committed receipts and unconfirmed task IDs for one prefix.

    The tree is a GitHub record for review, not proof of Mac execution,
    workflow authority or absence of old offline browser effects.
    """
    if enabled is not True:
        raise PermissionError("Agent-control history discovery is default-disabled")
    if not isinstance(task_id_prefix, str) or _ID_PREFIX.fullmatch(task_id_prefix) is None:
        raise ValueError("Agent-control task prefix must be exact and bounded")
    if (
        not isinstance(independently_pinned_control_sha, str)
        or receipt._SHA_RE.fullmatch(independently_pinned_control_sha) is None
        or not isinstance(independently_pinned_source_sha, str)
        or receipt._SHA_RE.fullmatch(independently_pinned_source_sha) is None
        or not isinstance(expected_agent_binding, str)
        or receipt._BINDING_RE.fullmatch(expected_agent_binding) is None
        or not isinstance(expected_work_branch, str)
        or not expected_work_branch.startswith("work/")
        or not re.fullmatch(r"work/[A-Za-z0-9._/-]{1,195}", expected_work_branch)
        or ".." in expected_work_branch
        or "//" in expected_work_branch
        or expected_work_branch.endswith("/")
    ):
        raise ValueError("Agent-control history source pins invalid")
    if api is not None and token is not None:
        raise ValueError("Agent-control history accepts API or token, not both")
    remote = receipt._GetOnly(api if api is not None else git.GitHubFabricREST(token))
    commit = remote.request("GET", f"/git/commits/{independently_pinned_control_sha}")
    if not isinstance(commit, dict) or not isinstance(commit.get("tree"), dict):
        raise ValueError("Agent-control history commit metadata invalid")
    tree_sha = git._require_sha(commit["tree"].get("sha"), label="history tree")
    snapshot = remote.request("GET", f"/git/trees/{tree_sha}?recursive=1")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("truncated") is not False
        or not isinstance(snapshot.get("tree"), list)
        or len(snapshot["tree"]) > MAX_GIT_TREE_ENTRIES
    ):
        raise ValueError("Agent-control history Git tree incomplete or too large")

    scoped: dict[str, set[str]] = {"task": set(), "result": set()}
    scoped_paths: dict[str, str] = {}
    for entry in snapshot["tree"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("Agent-control history has malformed Git tree entry")
        path = entry["path"]
        role = (
            "task" if path.startswith(_TASK_ROOT + task_id_prefix)
            else "result" if path.startswith(_RESULT_ROOT + task_id_prefix)
            else None
        )
        if role is None:
            continue
        root = _TASK_ROOT if role == "task" else _RESULT_ROOT
        relative = path[len(root):]
        if not relative.endswith(".json"):
            # Payload directories or unexpected nested paths are not eligible
            # to be silently skipped during a read-only scoped audit.
            raise ValueError("Agent-control history has unexpected scoped path")
        task_id = relative[:-5]
        if (
            receipt._TASK_RE.fullmatch(task_id) is None
            or entry.get("type") != "blob"
            or entry.get("mode") != "100644"
            or not isinstance(entry.get("sha"), str)
            or receipt._SHA_RE.fullmatch(entry["sha"]) is None
            or path in scoped_paths
        ):
            raise ValueError("Agent-control history scoped Git entry invalid")
        scoped_paths[path] = entry["sha"]
        scoped[role].add(task_id)

    if len(scoped["task"] | scoped["result"]) > MAX_SCOPED_TASKS:
        raise ValueError("Agent-control history task scope exceeds bound")
    if not scoped["result"].issubset(scoped["task"]):
        raise ValueError("Agent-control history has orphan result without task")
    class _TreePinnedAPI:
        def request(self, method: str, path: str, body: Any = None) -> dict[str, Any]:
            if method != "GET" or body is not None:
                raise PermissionError("Agent-control tree-pinned recovery forbids mutation")
            response = remote.request("GET", path)
            if path.startswith("/contents/"):
                relative, sep, ref = path[len("/contents/"):].partition("?ref=")
                if (
                    not sep or ref != independently_pinned_control_sha
                    or relative not in scoped_paths
                    or not isinstance(response, dict)
                    or response.get("sha") != scoped_paths[relative]
                ):
                    raise ValueError("Agent-control Contents blob differs from pinned Git tree")
            return response

    tree_api = _TreePinnedAPI()
    found = tuple(
        receipt.recover_agent_control_result(
            task_id,
            independently_pinned_control_sha=independently_pinned_control_sha,
            independently_pinned_source_sha=independently_pinned_source_sha,
            expected_agent_binding=expected_agent_binding,
            expected_work_branch=expected_work_branch,
            enabled=True,
            api=tree_api,
        )
        for task_id in sorted(scoped["result"])
    )
    return AgentControlReadOnlyHistory(
        control_commit_sha=independently_pinned_control_sha,
        source_commit_sha=independently_pinned_source_sha,
        expected_work_branch=expected_work_branch,
        selected_task_prefix=task_id_prefix,
        result_observations=found,
        unconfirmed_task_ids=tuple(sorted(scoped["task"] - scoped["result"])),
    )
