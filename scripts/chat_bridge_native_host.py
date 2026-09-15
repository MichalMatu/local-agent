#!/usr/bin/env python3
"""Install or inspect the macOS Chrome Native Messaging registration for Chat Bridge."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from local_agent.paths import repository_root

HOST_NAME = "com.michalmatu.local_agent_bridge"
_EXTENSION_ID_RE = re.compile(r"^[a-p]{32}$")
CHROME_HOST_DIR = (
    Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "NativeMessagingHosts"
)
LOCAL_HOST_DIR = Path.home() / "Library" / "Application Support" / "local-agent" / "native-host"
WRAPPER_PATH = LOCAL_HOST_DIR / "local-agent-chat-bridge-host"
MANIFEST_PATH = CHROME_HOST_DIR / f"{HOST_NAME}.json"


def validate_extension_id(value: str) -> str:
    extension_id = value.strip().lower()
    if not _EXTENSION_ID_RE.fullmatch(extension_id):
        raise ValueError("extension id must be exactly 32 lowercase Chrome id characters a-p")
    return extension_id


def wrapper_text() -> str:
    python = shlex.quote(str(Path(sys.executable).resolve()))
    root = shlex.quote(str(repository_root().resolve()))
    return (
        "#!/bin/sh\n"
        f"export PYTHONPATH={root}${{PYTHONPATH:+:$PYTHONPATH}}\n"
        f"exec {python} -m local_agent.platform.chrome_native_host \"$@\"\n"
    )


def manifest_payload(extension_id: str) -> dict[str, object]:
    return {
        "name": HOST_NAME,
        "description": "Local Agent Chat Bridge result event transport",
        "path": str(WRAPPER_PATH.resolve()),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }


def install(extension_id: str) -> None:
    extension_id = validate_extension_id(extension_id)
    LOCAL_HOST_DIR.mkdir(parents=True, exist_ok=True)
    CHROME_HOST_DIR.mkdir(parents=True, exist_ok=True)

    WRAPPER_PATH.write_text(wrapper_text(), encoding="utf-8")
    os.chmod(WRAPPER_PATH, 0o700)
    MANIFEST_PATH.write_text(
        json.dumps(manifest_payload(extension_id), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.chmod(MANIFEST_PATH, 0o600)
    print(MANIFEST_PATH)


def uninstall() -> None:
    for path in (MANIFEST_PATH, WRAPPER_PATH):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def status() -> int:
    payload: dict[str, object] | None = None
    if MANIFEST_PATH.exists():
        try:
            parsed = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                payload = parsed
        except (OSError, json.JSONDecodeError):
            payload = None
    print(
        json.dumps(
            {
                "manifest": str(MANIFEST_PATH),
                "manifest_exists": MANIFEST_PATH.exists(),
                "wrapper": str(WRAPPER_PATH),
                "wrapper_exists": WRAPPER_PATH.exists(),
                "registered_path": payload.get("path") if payload else None,
                "allowed_origins": payload.get("allowed_origins") if payload else None,
            },
            indent=2,
        )
    )
    return 0 if MANIFEST_PATH.exists() and WRAPPER_PATH.exists() and payload else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--extension-id", required=True)
    subparsers.add_parser("uninstall")
    subparsers.add_parser("status")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "install":
        try:
            install(args.extension_id)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0
    if args.command == "uninstall":
        uninstall()
        return 0
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
