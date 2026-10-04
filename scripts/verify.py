#!/usr/bin/env python3
"""Run Local Agent verification profiles."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MACOS_SMOKE_TESTS = [
    "tests.test_runner_process",
    "tests.test_checkpoint",
    "tests.test_multi_repository",
    "tests.test_binding",
    "tests.test_emergency_control",
    "tests.test_mcp",
]


def _require(command: str) -> str:
    resolved = shutil.which(command)
    if resolved is None:
        raise RuntimeError(f"required command is unavailable: {command}")
    return resolved


def _run(label: str, command: list[str]) -> None:
    print(f"\n==> {label}", flush=True)
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def run_compile() -> None:
    _run("Python compile", [sys.executable, "-m", "compileall", "-q", "local_agent", "scripts", "tests"])


def run_lint() -> None:
    ruff = _require("ruff")
    _run("Ruff", [ruff, "check", "."])


def run_bridge() -> None:
    node = _require("node")
    _run("Chat Bridge manifest", [node, "--check", "chat_bridge/service_worker.js"])
    _run("Chat Bridge content", [node, "--check", "chat_bridge/content.js"])
    _run("Chat Bridge content retry", [node, "--check", "chat_bridge/content_retry.js"])
    _run("Chat Bridge DOM contract", [node, "--check", "chat_bridge/dom_contract.js"])
    _run("Chat Bridge exhaustion guard", [node, "--check", "chat_bridge/exhaustion_guard.js"])
    _run("Chat Bridge control protocol", [node, "--check", "chat_bridge/control_protocol.js"])
    _run("Chat Bridge worker spawn", [node, "--check", "chat_bridge/worker_spawn.js"])
    _run("Chat Bridge popup", [node, "--check", "chat_bridge/popup.js"])
    _run("Conversation live browser actuator", [node, "--check", "scripts/conversation_live_slice_browser.cjs"])


def run_tests() -> None:
    _run("Unit and integration tests", [sys.executable, "-m", "unittest", "discover", "-q"])


def run_macos_smoke() -> None:
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
    # Child-conversation spawning is now intentionally direct browser DOM control.
    # The old conversation_spawn_* extension-worker smokes exercised a second,
    # obsolete spawn implementation and could block the real path without adding
    # coverage. Keep one end-to-end restart/recovery/direct-submit smoke here.
    _run(
        "Conversation direct browser restart/recovery smoke",
        [node, "scripts/conversation_live_slice_browser_smoke.cjs"],
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
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.only == "compile":
        run_compile()
        return 0
    if args.only == "lint":
        run_lint()
        return 0
    if args.only == "bridge":
        run_bridge()
        return 0
    if args.only == "tests":
        run_tests()
        return 0

    if args.profile == "macos-smoke":
        run_macos_smoke()
        return 0
    if args.profile == "bridge-browser":
        run_bridge_browser()
        return 0

    run_compile()
    run_lint()
    run_bridge()
    run_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
