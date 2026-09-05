#!/usr/bin/env python3
"""Render, install and inspect the Local Agent macOS LaunchAgent."""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_agent.platform.macos_launchd import (  # noqa: E402
    LABEL,
    bootout,
    bootstrap,
    default_launch_agent_path,
    print_status,
    render_launch_agent,
    validate_checkout,
    write_launch_agent,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("render", "install", "restart", "status", "uninstall"),
    )
    parser.add_argument(
        "--mode",
        choices=("parallel", "multirepo", "single"),
        default="parallel",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--output", type=Path)
    return parser


def _require_macos() -> None:
    if platform.system() != "Darwin":
        raise SystemExit("this command requires macOS")


def _render(args: argparse.Namespace) -> bytes:
    return render_launch_agent(
        args.mode,
        repo_root=args.repo_root,
        home=args.home,
        max_workers=args.max_workers,
        registry_path=args.registry,
    )


def main() -> int:
    args = _parser().parse_args()
    plist_path = args.output or default_launch_agent_path(args.home)

    if args.command == "render":
        content = _render(args)
        if args.output:
            write_launch_agent(plist_path, content)
            print(plist_path)
        else:
            sys.stdout.buffer.write(content)
        return 0

    _require_macos()

    if args.command == "status":
        result = print_status()
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    if args.command == "uninstall":
        bootout(check=False)
        plist_path.unlink(missing_ok=True)
        print(f"removed {plist_path}")
        return 0

    validate_checkout(args.repo_root)

    if args.command == "install":
        write_launch_agent(plist_path, _render(args))
        print(f"installed {plist_path}")
        print(
            f"not activated; run: {sys.executable} scripts/macos_launchd.py restart"
        )
        return 0

    if args.command == "restart":
        write_launch_agent(plist_path, _render(args))
        bootout(check=False)
        bootstrap(plist_path)
        print(f"restarted {LABEL} from {plist_path}")
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
