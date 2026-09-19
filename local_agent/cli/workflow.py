#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from local_agent.workflow import contract, methods, preview, store


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("workflow manifest must be an object")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect and manage Local Agent workflows.")
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Override the Local Agent application state directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("methods", help="List built-in workflow methods.")

    method_parser = subparsers.add_parser(
        "method",
        help="Show one built-in workflow method and its pinned digest.",
    )
    method_parser.add_argument("name")
    method_parser.add_argument("--version", type=int)

    validate_parser = subparsers.add_parser(
        "validate-manifest",
        help="Validate a workflow manifest without executing it.",
    )
    validate_parser.add_argument("path", type=Path)

    preview_parser = subparsers.add_parser(
        "preview-manifest",
        help="Preview task waves and waits without persisting or executing the workflow.",
    )
    preview_parser.add_argument("path", type=Path)

    submit_parser = subparsers.add_parser(
        "submit",
        help="Persist an immutable local workflow without dispatching repository tasks.",
    )
    submit_parser.add_argument("path", type=Path)

    subparsers.add_parser("list", help="List persisted local workflow ids.")

    show_parser = subparsers.add_parser("show", help="Show one persisted workflow.")
    show_parser.add_argument("workflow_id")

    resolve_parser = subparsers.add_parser(
        "resolve-gate",
        help="Resolve one waiting user gate with an exactly-once durable decision.",
    )
    resolve_parser.add_argument("workflow_id")
    resolve_parser.add_argument("node_id")
    resolve_parser.add_argument("decision")
    resolve_parser.add_argument("--resolver", default="local-operator")

    checkpoint_parser = subparsers.add_parser(
        "resolve-checkpoint",
        help="Resolve one planner checkpoint after explicit evidence review.",
    )
    checkpoint_parser.add_argument("workflow_id")
    checkpoint_parser.add_argument("node_id")
    checkpoint_parser.add_argument("--resolver", default="chatgpt-planner")
    checkpoint_parser.add_argument("--note")

    cancel_parser = subparsers.add_parser(
        "cancel",
        help="Request workflow cancellation without killing unrelated work.",
    )
    cancel_parser.add_argument("workflow_id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "methods":
        for spec in methods.list_builtin_methods():
            print(
                f"{spec['name']}\tversion={spec['version']}\t"
                f"{methods.method_digest(spec)}"
            )
        return 0

    if args.command == "method":
        try:
            spec = methods.load_builtin_method(args.name, version=args.version)
        except ValueError as exc:
            _print_json({"error": str(exc)})
            return 2
        _print_json(
            {
                "name": spec["name"],
                "version": spec["version"],
                "digest": methods.method_digest(spec),
                "spec": spec,
            }
        )
        return 0

    if args.command == "validate-manifest":
        try:
            payload = _load_manifest(args.path)
            contract.validate_workflow_manifest(payload)
            digest = contract.manifest_digest(payload)
        except Exception as exc:
            _print_json(
                {
                    "valid": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return 2
        _print_json(
            {
                "valid": True,
                "workflow_id": payload["id"],
                "manifest_digest": digest,
                "node_count": len(payload["nodes"]),
            }
        )
        return 0

    if args.command == "preview-manifest":
        try:
            payload = _load_manifest(args.path)
            result = preview.preview_workflow(payload)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json(
            {
                "workflow_id": payload["id"],
                "waves": [list(wave) for wave in result.waves],
                "final_state": result.final_state,
                "waiting_nodes": list(result.waiting_nodes),
            }
        )
        return 0

    workflow_store = store.WorkflowStore(args.state_dir)

    if args.command == "submit":
        try:
            payload = _load_manifest(args.path)
            result = workflow_store.submit(payload)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json(result)
        return 0

    if args.command == "list":
        _print_json({"workflow_ids": workflow_store.workflow_ids()})
        return 0

    if args.command == "show":
        try:
            manifest = workflow_store.load_manifest(args.workflow_id)
            current_state = workflow_store.load_state(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json({"manifest": manifest, "state": current_state})
        return 0

    if args.command == "resolve-gate":
        try:
            decision = workflow_store.resolve_user_gate(
                args.workflow_id,
                args.node_id,
                args.decision,
                resolver=args.resolver,
            )
            current_state = workflow_store.load_state(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json({"decision": decision, "state": current_state})
        return 0

    if args.command == "resolve-checkpoint":
        try:
            resolution = workflow_store.resolve_planner_checkpoint(
                args.workflow_id,
                args.node_id,
                resolver=args.resolver,
                note=args.note,
            )
            current_state = workflow_store.load_state(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json({"resolution": resolution, "state": current_state})
        return 0

    if args.command == "cancel":
        try:
            result = workflow_store.cancel(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json(result)
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
