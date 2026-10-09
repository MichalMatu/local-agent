"""Offline, no-Bridge operator tools for synthetic handoff and test-task review.

Run as: python -m scripts.no_bridge_manual {export,inspect,plan-test} ...
No GitHub/ChatGPT/Local Agent calls or filesystem writes occur here.
A manifest digest and a user-supplied SHA are not source authentication.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from local_agent.conversation import github_fabric_manual_handoff as handoff
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


def _strict_observation(text: str) -> dict[str, Any]:
    def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate observation field")
            obj[key] = value
        return obj

    def _reject_constant(_value: str) -> None:
        raise ValueError("Non-finite JSON observation value")

    try:
        decoded = json.loads(
            text, object_pairs_hook=_unique_fields,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError("Input is not JSON") from exc
    if type(decoded) is not dict:
        raise ValueError("Observation must be a JSON object")
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
    except (OSError, ValueError, PermissionError) as exc:
        # Error messages are source-free and never contain input JSON or token text.
        print(f"Manual no-Bridge review refused: {type(exc).__name__}", file=sys.stderr)
        return 2
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
