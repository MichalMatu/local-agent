#!/usr/bin/env python3
"""Run deterministic Local Agent verification stages."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYTHON_SOURCES = [
    "agentd.py",
    "agent_entrypoint.py",
    "agent_multirepo.py",
    "agent_parallel.py",
    "local_agent",
    "scripts",
    "tests",
]

MACOS_SMOKE_TESTS = [
    "tests.test_foundation_process",
    "tests.test_process_tree_cleanup",
    "tests.test_process_tree_escape_cleanup",
    "tests.test_stale_claims",
    "tests.test_multi_repository",
    "tests.test_repository_identity",
    "tests.test_agent_binding",
    "tests.test_remote_operator",
    "tests.test_operator_control",
]


def _require(command: str) -> str:
    found = shutil.which(command)
    if not found:
        raise SystemExit(f"required command not found: {command}")
    return found


def _run(label: str, argv: list[str]) -> None:
    print(f"\n==> {label}")
    subprocess.run(argv, cwd=ROOT, check=True)


def compile_sources() -> None:
    _run(
        "Python compile",
        [sys.executable, "-m", "compileall", "-q", *PYTHON_SOURCES],
    )


def lint_sources() -> None:
    ruff = _require("ruff")
    _run("Ruff", [ruff, "check", "."])


def validate_bridge() -> None:
    node = _require("node")
    bridge_dir = ROOT / "chat_bridge"

    javascript = sorted(bridge_dir.glob("*.js"))
    for path in javascript:
        _run(
            f"Node syntax: {path.name}",
            [node, "--check", path.relative_to(ROOT).as_posix()],
        )

    for path in sorted(bridge_dir.glob("*.test.js")):
        _run(
            f"Node test: {path.name}",
            [node, path.relative_to(ROOT).as_posix()],
        )

    json_files = sorted(bridge_dir.glob("*.json")) + sorted((ROOT / "config").glob("*.json"))
    for path in json_files:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
        print(f"validated JSON: {path.relative_to(ROOT)}")


def run_tests() -> None:
    _run("Python unit and integration tests", [sys.executable, "-m", "unittest", "discover", "-q"])


def run_macos_smoke() -> None:
    compile_sources()
    _run(
        "macOS focused smoke suite",
        [sys.executable, "-m", "unittest", "-q", *MACOS_SMOKE_TESTS],
    )


def run_bridge_browser() -> None:
    node = _require("node")
    _run("Chromium extension smoke", [node, "scripts/bridge_browser_smoke.cjs"])
    _run("Chromium assistant timeout recovery smoke", [node, "scripts/bridge_assistant_error_smoke.cjs"])
    _run(
        "Chromium assistant timeout resilience smoke",
        [node, "scripts/bridge_assistant_error_resilience_smoke.cjs"],
    )
    _run(
        "Chromium operator timeout fail-closed smoke",
        [node, "scripts/bridge_assistant_error_unowned_smoke.cjs"],
    )
    _run(
        "Chromium assistant timeout page-reload smoke",
        [node, "scripts/bridge_assistant_error_reload_smoke.cjs"],
    )
    _run(
        "Chromium transient assistant recovery smoke",
        [node, "scripts/bridge_transient_recovery_smoke.cjs"],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=("compile", "lint", "bridge", "tests"),
        help="run one verification stage instead of the full suite",
    )
    parser.add_argument(
        "--profile",
        choices=("full", "macos-smoke", "bridge-browser"),
        default="full",
        help="verification profile; default: full",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.only:
        stages = {
            "compile": compile_sources,
            "lint": lint_sources,
            "bridge": validate_bridge,
            "tests": run_tests,
        }
        stages[args.only]()
        return 0

    if args.profile == "macos-smoke":
        run_macos_smoke()
        return 0
    if args.profile == "bridge-browser":
        run_bridge_browser()
        return 0

    compile_sources()
    lint_sources()
    validate_bridge()
    run_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
