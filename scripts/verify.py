#!/usr/bin/env python3
"""Repository verification entrypoint.

Keep command discovery and focused smoke-test selection in one place so CI,
operator docs and local development do not maintain diverging file lists.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MACOS_SMOKE_TESTS = (
    "tests.test_package_layout",
    "tests.test_release_hardening",
    "tests.test_guard_process",
    "tests.test_agent_multirepo_restart",
    "tests.test_agentd_dispatch",
    "tests.test_self_update_environment",
    "tests.test_macos_launchd",
    "tests.test_remote_operator",
    "tests.test_agent_process",
    "tests.test_agent_core",
    "tests.test_agent_runtime",
    "tests.test_agent_storage",
    "tests.test_agent_binding",
    "tests.test_serial_agent_binding",
    "tests.test_agent_repo_worker",
    "tests.test_agent_parallel",
    "tests.test_agent_parallel_worker",
    "tests.test_parallel_control",
    "tests.test_parallel_process",
    "tests.test_multirepo_integration",
    "tests.test_parallel_integration",
    "tests.test_parallel_resource_wait",
    "tests.test_control_hardening",
    "tests.test_supervisor_modules",
    "tests.test_emergency_controls",
    "tests.test_entrypoint_guard",
)


def _run(label: str, command: list[str]) -> None:
    printable = " ".join(command)
    print(f"\n==> {label}\n$ {printable}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _require(executable: str) -> str:
    resolved = shutil.which(executable)
    if resolved is None:
        raise SystemExit(f"required executable not found on PATH: {executable}")
    return resolved


def _python_sources() -> list[str]:
    roots = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("*.py")
        if path.name.startswith("agent")
    )
    package = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "local_agent").rglob("*.py")
    )
    scripts = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "scripts").rglob("*.py")
    )
    return roots + package + scripts


def compile_sources() -> None:
    sources = _python_sources()
    if not sources:
        raise SystemExit("no Python sources discovered for compile verification")
    _run("Compile Python sources", [sys.executable, "-m", "py_compile", *sources])


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=("compile", "lint", "bridge", "tests"),
        help="run one verification stage instead of the full suite",
    )
    parser.add_argument(
        "--profile",
        choices=("full", "macos-smoke"),
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

    compile_sources()
    lint_sources()
    validate_bridge()
    run_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
