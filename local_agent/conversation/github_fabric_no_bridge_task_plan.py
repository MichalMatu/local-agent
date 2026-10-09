"""Deterministic, no-Bridge Local Agent source-test task *planner*.

The returned JSON is not published or executed. The caller must independently
check its target repo, binding, PR head and daemon before any GitHub mutation.
This generates read-only test tasks only, never browser Send or arbitrary
repository execution, and uses no Codex/Chat Bridge/Actions.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from local_agent.conversation import github_fabric_agent_control_recovery as evidence
from local_agent.runtime import task_contract

_JOB_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_BRANCH_RE = re.compile(r"work/[A-Za-z0-9._/-]{1,195}\Z")


@dataclass(frozen=True, slots=True)
class NoBridgeVerificationTaskPlan:
    task_id: str
    source_sha: str
    branch: str
    profile: str
    task_json: str
    task_digest: str
    decision: str = "manual_publication_review_only"
    published: bool = False
    executing: bool = False
    browser_effects_permitted: bool = False
    automatic_retry_permitted: bool = False
    binding_recheck_required: bool = True


def plan_no_bridge_source_test(
    *,
    task_job_id: str,
    exact_source_sha: str,
    work_branch: str,
    independently_verified_agent_binding: str,
    profile: str = "core",
    operator_review_acknowledged: bool = False,
) -> NoBridgeVerificationTaskPlan:
    """Plan one exact-head local-agent Mac verification task with no side effect."""
    if operator_review_acknowledged is not True:
        raise PermissionError("No-Bridge task planning requires manual review opt-in")
    if not isinstance(task_job_id, str) or _JOB_RE.fullmatch(task_job_id) is None:
        raise ValueError("No-Bridge task job identity invalid")
    if not isinstance(exact_source_sha, str) or evidence._SHA_RE.fullmatch(
        exact_source_sha
    ) is None:
        raise ValueError("No-Bridge task source SHA invalid")
    if (
        not isinstance(work_branch, str)
        or _BRANCH_RE.fullmatch(work_branch) is None
        or ".." in work_branch
        or "//" in work_branch
        or work_branch.endswith("/")
    ):
        raise ValueError("No-Bridge task work branch invalid")
    if not isinstance(independently_verified_agent_binding, str) or evidence._BINDING_RE.fullmatch(
        independently_verified_agent_binding
    ) is None:
        raise ValueError("No-Bridge task binding invalid")
    if profile not in ("core", "full"):
        raise ValueError("No-Bridge task verification profile unsupported")

    material = json.dumps(
        ["no-bridge-local-agent-source-test-v1", task_job_id, work_branch,
         exact_source_sha, profile, independently_verified_agent_binding],
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    suffix = hashlib.sha256(material).hexdigest()[:16]
    task_id = f"local-agent-nobridge-{profile}-{suffix}"
    command = (
        'set -euo pipefail\n'
        f'test "$(git rev-parse HEAD)" = "{exact_source_sha}" || exit 3\n'
        'test -z "$(git status --porcelain)" || exit 4\n'
        'python3.13 scripts/verify_local.py '
        f'--expected-sha "{exact_source_sha}" --profile {profile}\n'
    )
    task = {
        "id": task_id,
        "dedupe_key": f"local-agent/m8/nobridge-source-test/{suffix}",
        "dedupe_revision": 1,
        "agent_binding": independently_verified_agent_binding,
        "mode": "commands",
        "work_branch": work_branch,
        "allow_write": False,
        "resources": [],
        "memory_limit_mb": 4096 if profile == "full" else 1024,
        "command_timeout": 1800 if profile == "full" else 900,
        "task_timeout": 3000 if profile == "full" else 1200,
        "idle_timeout": 300 if profile == "full" else 180,
        "commands": [command],
    }
    task_contract.validate_task(task, require_agent_binding=True)
    task_digest = task_contract.task_digest(task)
    return NoBridgeVerificationTaskPlan(
        task_id=task_id,
        source_sha=exact_source_sha,
        branch=work_branch,
        profile=profile,
        task_json=json.dumps(task, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        task_digest=task_digest,
    )
