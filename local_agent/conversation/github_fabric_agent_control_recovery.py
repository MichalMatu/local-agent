"""GET-only, commit-pinned agent-control task/result evidence reader.

This exposes bounded, redacted *reported* test outcomes for operator review.
A GitHub record is not an attestation of physical command execution. No
result may authorize retries, repository work, browser effects or ACK.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from local_agent.conversation import github_fabric_github as git

_TASK_RE = re.compile(r"[A-Za-z0-9._-]{1,200}\Z")
_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_BINDING_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
_TASK_LIMIT = 32768
_RESULT_LIMIT = 262144


@dataclass(frozen=True, slots=True)
class AgentControlReadOnlyObservation:
    task_id: str
    control_commit_sha: str
    source_commit_sha: str
    work_branch: str
    task_digest: str
    reported_status: str
    reported_outcome: str
    command_count: int
    write_disabled_in_task_record: bool = True
    command_effects_independently_verified: bool = False
    output_disclosed: bool = False
    effect_authorized: bool = False
    automatic_retry_permitted: bool = False
    result_execution_attested: bool = False


class _GetOnly:
    def __init__(self, api: Any) -> None:
        self._api = api

    def request(self, method: str, path: str, body: Any = None) -> dict[str, Any]:
        if method != "GET" or body is not None:
            raise PermissionError("Agent-control recovery forbids mutations")
        return self._api.request("GET", path)


def _blob_json(api: _GetOnly, path: str, head: str, max_bytes: int) -> dict[str, Any]:
    response = api.request("GET", f"/contents/{quote(path, safe='/')}?ref={head}")
    if (
        not isinstance(response, dict) or response.get("type") != "file"
        or response.get("encoding") != "base64"
        or type(response.get("size")) is not int
        or not 0 <= response["size"] <= max_bytes
        or not isinstance(response.get("content"), str)
        or not isinstance(response.get("sha"), str)
        or _SHA_RE.fullmatch(response["sha"]) is None
    ):
        raise ValueError("Agent-control file metadata invalid")
    try:
        raw = base64.b64decode(response["content"].replace("\n", ""), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Agent-control base64 data invalid") from exc
    if len(raw) != response["size"] or len(raw) > max_bytes:
        raise ValueError("Agent-control payload exceeds declared size")
    expected_blob_sha = hashlib.sha1(
        f"blob {len(raw)}\0".encode("ascii") + raw
    ).hexdigest()
    if expected_blob_sha != response["sha"]:
        raise ValueError("Agent-control Git blob identity mismatch")
    def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Agent-control JSON contains duplicate fields")
            value[key] = item
        return value

    def _reject_constant(_constant: str) -> Any:
        raise ValueError("Agent-control JSON contains a non-finite number")

    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Agent-control JSON invalid") from exc
    if type(payload) is not dict:
        raise ValueError("Agent-control record must be a JSON object")
    return payload


def _task_digest(task: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        task, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def _validate_scoped_task(
    task: dict[str, Any], *,
    task_id: str,
    source_sha: str,
    binding: str,
    work_branch: str,
) -> list[str]:
    """Require a guarded task that *declares* no writes, not a shell sandbox."""
    commands = task.get("commands")
    guard = (
        'set -euo pipefail\n'
        f'test "$(git rev-parse HEAD)" = "{source_sha}" || exit 3\n'
        'test -z "$(git status --porcelain)" || exit 4\n'
    )
    if (
        task.get("id") != task_id or task.get("agent_binding") != binding
        or task.get("work_branch") != work_branch
        or task.get("allow_write") is not False
        or task.get("resources") != []
        or task.get("mode") != "commands"
        or type(commands) is not list or len(commands) != 1
        or any(not isinstance(command, str) for command in commands)
        or not commands[0].startswith(guard)
        or any(field in task for field in (
            "steps", "verify_steps", "patch", "writes", "deletes", "verify_commands",
        ))
    ):
        raise ValueError("Agent-control task is outside read-only exact-head scope")
    return commands


def recover_agent_control_result(
    task_id: str, *,
    independently_pinned_control_sha: str,
    independently_pinned_source_sha: str,
    expected_agent_binding: str,
    expected_work_branch: str,
    enabled: bool = False,
    token: str | None = None,
    api: Any | None = None,
) -> AgentControlReadOnlyObservation:
    """Reconcile one task/result from one explicitly pinned agent-control commit.

    Every identifier is operator-pinned, not learned from browser metadata.
    Only a task that *declares* allow_write=false and carries an exact-head
    checkout guard is eligible. The command string is not sandboxed here.
    """
    if enabled is not True:
        raise PermissionError("Agent-control recovery is default-disabled")
    if not isinstance(task_id, str) or _TASK_RE.fullmatch(task_id) is None:
        raise ValueError("Agent-control task ID invalid")
    if not isinstance(independently_pinned_control_sha, str) or _SHA_RE.fullmatch(
        independently_pinned_control_sha
    ) is None:
        raise ValueError("Agent-control origin commit SHA invalid")
    if not isinstance(independently_pinned_source_sha, str) or _SHA_RE.fullmatch(
        independently_pinned_source_sha
    ) is None:
        raise ValueError("Agent-control task source commit SHA invalid")
    if not isinstance(expected_agent_binding, str) or _BINDING_RE.fullmatch(
        expected_agent_binding
    ) is None:
        raise ValueError("Agent-control binding pin invalid")
    if (
        not isinstance(expected_work_branch, str)
        or not expected_work_branch.startswith("work/")
        or len(expected_work_branch) > 200
        or not re.fullmatch(r"work/[A-Za-z0-9._/-]{1,195}", expected_work_branch)
        or ".." in expected_work_branch
        or "//" in expected_work_branch
        or expected_work_branch.endswith("/")
    ):
        raise ValueError("Agent-control branch pin invalid")
    if api is not None and token is not None:
        raise ValueError("Agent-control recovery requires API or token, not both")
    remote = _GetOnly(api if api is not None else git.GitHubFabricREST(token))
    commit = remote.request("GET", f"/git/commits/{independently_pinned_control_sha}")
    if not isinstance(commit, dict) or not isinstance(commit.get("tree"), dict):
        raise ValueError("Agent-control commit metadata invalid")
    if commit.get("sha") != independently_pinned_control_sha:
        raise ValueError("Agent-control Git commit identity mismatch")
    git._require_sha(commit["tree"].get("sha"), label="agent-control tree")
    task = _blob_json(
        remote, f".agent/tasks/{task_id}.json",
        independently_pinned_control_sha, _TASK_LIMIT,
    )
    result = _blob_json(
        remote, f".agent/results/{task_id}.json",
        independently_pinned_control_sha, _RESULT_LIMIT,
    )
    commands = _validate_scoped_task(
        task, task_id=task_id,
        source_sha=independently_pinned_source_sha,
        binding=expected_agent_binding,
        work_branch=expected_work_branch,
    )
    digest = _task_digest(task)
    if (
        not isinstance(result.get("task_digest"), str)
        or _DIGEST_RE.fullmatch(result["task_digest"]) is None
        or result["task_digest"] != digest
        or result.get("id") != task_id
        or result.get("work_branch") != expected_work_branch
        or result.get("allow_write") is not False
        or result.get("mode") != "commands"
        or not isinstance(result.get("commands"), list)
        or len(result["commands"]) != len(commands)
    ):
        raise ValueError("Agent-control result/task association invalid")
    for command, observation in zip(commands, result["commands"]):
        if type(observation) is not dict or observation.get("command") != command:
            raise ValueError("Agent-control reported command identity mismatch")

    reported_core_pass = (
        result.get("status") == "done"
        and result.get("edits") == {}
        and result.get("verification") == []
        and all(
            isinstance(result.get(field), dict)
            and type(result[field].get("exit_code")) is int
            and result[field]["exit_code"] == 0
            and result[field].get("output") == ""
            for field in ("git_status", "git_diff")
        )
        and type(result.get("stages")) is list
        and len(result["stages"]) == len(commands)
        and all(
            isinstance(item, dict)
            and item.get("outcome") == "passed"
            and item.get("stage_phase") == "commands"
            and type(item.get("stage_index")) is int
            and item["stage_index"] == index
            and type(item.get("stage_total")) is int
            and item["stage_total"] == len(commands)
            for index, item in enumerate(result["stages"], 1)
        )
        and all(
            type(entry) is dict
            and type(entry.get("exit_code")) is int
            and entry["exit_code"] == 0
            and entry.get("timed_out") is False
            and entry.get("idle_timed_out") is False
            and entry.get("memory_limited") is False
            and entry.get("background_process_leak") is False
            for entry in result["commands"]
        )
    )
    log_complete = all(
        type(entry) is dict and entry.get("output_truncated") is False
        for entry in result["commands"]
    )
    if result.get("status") not in (
        "done", "failed", "error", "cancelled", "canceled", "timed_out", "aborted", "running", "pending"
    ):
        raise ValueError("Agent-control reported status invalid")
    # A successfully completed test with truncated logs is neither an
    # authenticated full PASS nor evidence of a failed command. Keep that
    # distinction explicit and deny any execution/retry authority in all cases.
    outcome = (
        "reported_pass_for_review" if reported_core_pass and log_complete
        else "reported_incomplete_evidence_for_review" if reported_core_pass
        else "reported_nonpass_for_review"
    )
    return AgentControlReadOnlyObservation(
        task_id=task_id,
        control_commit_sha=independently_pinned_control_sha,
        source_commit_sha=independently_pinned_source_sha,
        work_branch=expected_work_branch,
        task_digest=digest,
        reported_status=result["status"],
        reported_outcome=outcome,
        command_count=len(commands),
    )
