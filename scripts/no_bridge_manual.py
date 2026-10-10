"""No-Bridge operator tools for synthetic handoff and test-task review.

Run as: python -m scripts.no_bridge_manual ACTION ...
Export, inspect and plan-test are offline; verify-github is explicit opt-in,
GET-only and known-public synthetic source-restricted. No file writes, Send,
Chat Bridge or Local Agent task execution ever occurs here.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from local_agent.conversation import github_fabric_manual_handoff as handoff
from local_agent.conversation import github_fabric_agent_control_index as history
from local_agent.conversation import github_fabric_agent_control_public_rest as public_rest
from local_agent.conversation import github_fabric_github as git
from local_agent.conversation import github_fabric_manual_new_parent as manual
from local_agent.conversation import github_fabric_no_bridge_task_plan as planner

MAX_INPUT_BYTES = 8192


def _load_bounded_text(path: str) -> str:
    if path == "-":
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    else:
        with Path(path).open("rb") as handle:
            raw = handle.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Input exceeds manual offline reader bound")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Input is not valid UTF-8") from exc


def _strict_observation(text: str, *, expected_list: bool = False) -> dict[str, Any] | list[Any]:
    def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate observation field")
            obj[key] = value
        return obj

    def _reject_constant(_value: str) -> None:
        raise ValueError("Non-finite JSON observation value")

    def _finite_float(raw_number: str) -> float:
        number = float(raw_number)
        if not math.isfinite(number):
            raise ValueError("Non-finite JSON observation value")
        return number

    try:
        decoded = json.loads(
            text, object_pairs_hook=_unique_fields,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Input is not JSON") from exc
    if type(decoded) is not (list if expected_list else dict):
        raise ValueError("Observation has an invalid JSON root type")
    return decoded


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline synthetic no-Bridge review; no GitHub or browser effects."
    )
    commands = parser.add_subparsers(dest="action", required=True)
    for name in ("export", "inspect"):
        command = commands.add_parser(name)
        command.add_argument(
            "--input", required=True, metavar="FILE_OR_DASH",
            help="Use '-' to read bounded UTF-8 JSON from standard input.",
        )
        command.add_argument("--pinned-source-sha", required=True)
        command.add_argument("--destination-parent-url", required=True)

    verified = commands.add_parser("verify-github")
    verified.add_argument("--manifest", required=True)
    verified.add_argument("--operator-request", required=True)
    verified.add_argument("--child-requests", required=True)
    verified.add_argument("--pinned-source-sha", required=True)
    verified.add_argument("--destination-parent-url", required=True)
    verified.add_argument("--allow-readonly-network", action="store_true")

    status = commands.add_parser("status-github")
    status.add_argument("--task-id-prefix", required=True)
    status.add_argument("--pinned-control-sha", required=True)
    status.add_argument("--pinned-source-sha", required=True)
    status.add_argument("--agent-binding", required=True)
    status.add_argument("--work-branch", required=True)
    status.add_argument("--allow-readonly-network", action="store_true")
    status.add_argument("--anonymous-public-read", action="store_true")

    planned = commands.add_parser("plan-test")
    planned.add_argument("--job-id", required=True)
    planned.add_argument("--source-sha", required=True)
    planned.add_argument("--work-branch", required=True)
    planned.add_argument("--agent-binding", required=True)
    planned.add_argument("--profile", choices=("core", "full"), default="core")
    planned.add_argument("--acknowledge-review", action="store_true")
    planned.add_argument("--approve-isolated-dependencies", action="store_true")
    return parser


def _execute(args: argparse.Namespace) -> str:
    if args.action == "export":
        observed = _strict_observation(_load_bounded_text(args.input))
        preview = manual.preview_manual_new_parent(
            observed,
            independently_pinned_source_sha=args.pinned_source_sha,
            destination_parent_conversation_url=args.destination_parent_url,
        )
        return handoff.export_manual_handoff(preview)
    if args.action == "inspect":
        parsed = handoff.import_manual_handoff(
            _load_bounded_text(args.input),
            independently_pinned_source_sha=args.pinned_source_sha,
            expected_destination_parent_conversation_url=args.destination_parent_url,
        )
        return json.dumps(asdict(parsed), sort_keys=True, separators=(",", ":"))
    if args.action == "verify-github":
        if args.allow_readonly_network is not True:
            raise PermissionError("Read-only GitHub verification requires opt-in")
        manifest = _load_bounded_text(args.manifest)
        operator_request = _strict_observation(
            _load_bounded_text(args.operator_request)
        )
        child_requests = _strict_observation(
            _load_bounded_text(args.child_requests), expected_list=True
        )
        # No token supplied through command-line arguments or source JSON.
        token = os.environ.get("LOCAL_AGENT_FABRIC_GITHUB_TOKEN")
        if not token:
            raise PermissionError("Read-only GitHub token is unavailable")
        result = handoff.verify_manual_handoff_against_github(
            manifest, operator_request, child_requests,
            independently_pinned_source_sha=args.pinned_source_sha,
            expected_destination_parent_conversation_url=args.destination_parent_url,
            enabled=True, token=token,
        )
        return json.dumps(asdict(result), sort_keys=True, separators=(",", ":"))
    if args.action == "status-github":
        if args.allow_readonly_network is not True:
            raise PermissionError("GitHub task history lookup requires explicit opt-in")
        # Anonymous access is permitted only for the hard-coded public repo.
        # It never reads environment credentials or crosses to other repos.
        if args.anonymous_public_read:
            token = None
            api = public_rest.PublicAgentControlReadOnlyREST()
        else:
            token = os.environ.get("LOCAL_AGENT_FABRIC_GITHUB_TOKEN")
            if not token:
                raise PermissionError("GitHub task history token unavailable")
            api = None
        found = history.discover_agent_control_results(
            task_id_prefix=args.task_id_prefix,
            independently_pinned_control_sha=args.pinned_control_sha,
            independently_pinned_source_sha=args.pinned_source_sha,
            expected_agent_binding=args.agent_binding,
            expected_work_branch=args.work_branch,
            enabled=True, token=token, api=api,
        )
        return json.dumps(asdict(found), sort_keys=True, separators=(",", ":"))
    if args.action == "plan-test":
        candidate = planner.plan_no_bridge_source_test(
            task_job_id=args.job_id,
            exact_source_sha=args.source_sha,
            work_branch=args.work_branch,
            independently_verified_agent_binding=args.agent_binding,
            profile=args.profile,
            operator_review_acknowledged=args.acknowledge_review,
            isolated_test_dependencies_approved=args.approve_isolated_dependencies,
        )
        # The exported JSON remains a plan, not a published .agent task.
        return json.dumps({
            "decision": candidate.decision,
            "published": candidate.published,
            "executing": candidate.executing,
            "binding_recheck_required": candidate.binding_recheck_required,
            "task_digest": candidate.task_digest,
            "task": json.loads(candidate.task_json),
        }, sort_keys=True, separators=(",", ":"))
    raise ValueError("Unsupported manual operation")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        rendered = _execute(args)
    except (
        OSError, ValueError, PermissionError,
        git.GithubFabricHTTPError, git.GithubFabricTransportError,
    ) as exc:
        # Error messages are source-free and never contain input JSON or token text.
        print(f"Manual no-Bridge review refused: {type(exc).__name__}", file=sys.stderr)
        return 2
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
