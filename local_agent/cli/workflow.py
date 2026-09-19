#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from local_agent.workflow import contract, methods


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Local Agent workflow contracts.")
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
            payload = json.loads(args.path.read_text(encoding="utf-8"))
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

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
