#!/usr/bin/env python3
"""Install or inspect the macOS Chrome Native Messaging registration for Chat Bridge."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST_NAME = "com.michalmatu.local_agent_bridge"
_EXTENSION_ID_RE = re.compile(r"^[a-p]{32}$")
_ORIGIN_RE = re.compile(r"^chrome-extension://([a-p]{32})/$")
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


def runtime_python() -> Path:
    installed = ROOT / ".venv" / "bin" / "python"
    if installed.is_file():
        return installed.resolve()
    return Path(sys.executable).resolve()


def wrapper_text() -> str:
    python = shlex.quote(str(runtime_python()))
    root = shlex.quote(str(ROOT.resolve()))
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


def _load_manifest() -> dict[str, object] | None:
    if not MANIFEST_PATH.is_file() or MANIFEST_PATH.is_symlink():
        return None
    try:
        parsed = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _origin_extension_id(payload: dict[str, object] | None) -> str | None:
    origins = payload.get("allowed_origins") if payload else None
    if not isinstance(origins, list) or len(origins) != 1 or not isinstance(origins[0], str):
        return None
    match = _ORIGIN_RE.fullmatch(origins[0])
    return match.group(1) if match else None


def status(expected_extension_id: str | None = None) -> int:
    if expected_extension_id is not None:
        expected_extension_id = validate_extension_id(expected_extension_id)
    payload = _load_manifest()
    problems: list[str] = []

    manifest_exists = MANIFEST_PATH.is_file() and not MANIFEST_PATH.is_symlink()
    wrapper_exists = WRAPPER_PATH.is_file() and not WRAPPER_PATH.is_symlink()
    wrapper_executable = wrapper_exists and os.access(WRAPPER_PATH, os.X_OK)
    wrapper_mode = stat.S_IMODE(WRAPPER_PATH.stat().st_mode) if wrapper_exists else None
    manifest_mode = stat.S_IMODE(MANIFEST_PATH.stat().st_mode) if manifest_exists else None
    registered_path = payload.get("path") if payload else None
    origin_extension_id = _origin_extension_id(payload)
    expected_wrapper = wrapper_text()
    wrapper_matches_expected = False
    if wrapper_exists:
        try:
            wrapper_matches_expected = WRAPPER_PATH.read_text(encoding="utf-8") == expected_wrapper
        except OSError:
            wrapper_matches_expected = False

    if not manifest_exists:
        problems.append("manifest_missing_or_not_regular")
    if payload is None:
        problems.append("manifest_invalid_json_or_shape")
    else:
        if payload.get("name") != HOST_NAME:
            problems.append("manifest_name_mismatch")
        if payload.get("type") != "stdio":
            problems.append("manifest_type_mismatch")
        if registered_path != str(WRAPPER_PATH.resolve()):
            problems.append("registered_path_mismatch")
        if origin_extension_id is None:
            problems.append("allowed_origin_invalid")
        elif expected_extension_id is not None and origin_extension_id != expected_extension_id:
            problems.append("allowed_origin_mismatch")
    if not wrapper_exists:
        problems.append("wrapper_missing_or_not_regular")
    else:
        if not wrapper_executable:
            problems.append("wrapper_not_executable")
        if not wrapper_matches_expected:
            problems.append("wrapper_content_mismatch")
    if wrapper_exists and wrapper_mode != 0o700:
        problems.append("wrapper_mode_unexpected")
    if manifest_exists and manifest_mode != 0o600:
        problems.append("manifest_mode_unexpected")

    healthy = not problems
    print(
        json.dumps(
            {
                "healthy": healthy,
                "problems": problems,
                "manifest": str(MANIFEST_PATH),
                "manifest_exists": manifest_exists,
                "manifest_mode": oct(manifest_mode) if manifest_mode is not None else None,
                "wrapper": str(WRAPPER_PATH),
                "wrapper_exists": wrapper_exists,
                "wrapper_executable": wrapper_executable,
                "wrapper_mode": oct(wrapper_mode) if wrapper_mode is not None else None,
                "wrapper_matches_expected": wrapper_matches_expected,
                "runtime_python": str(runtime_python()),
                "registered_path": registered_path,
                "allowed_origins": payload.get("allowed_origins") if payload else None,
                "registered_extension_id": origin_extension_id,
                "expected_extension_id": expected_extension_id,
            },
            indent=2,
        )
    )
    return 0 if healthy else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--extension-id", required=True)
    subparsers.add_parser("uninstall")
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--extension-id")
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
    try:
        return status(args.extension_id)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
