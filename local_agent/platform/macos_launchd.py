"""Generate and manage the macOS LaunchAgent definition for Local Agent."""

from __future__ import annotations

import os
import plistlib
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

LABEL = "com.michal.local-agent"
Mode = Literal["parallel", "multirepo", "single"]


def default_registry_path(home: Path) -> Path:
    return home / "Library" / "Application Support" / "local-agent" / "repositories.json"


def default_launch_agent_path(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def default_path(home: Path) -> str:
    return ":".join(
        (
            str(home / ".platformio" / "penv" / "bin"),
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        )
    )


def build_program_arguments(
    mode: Mode,
    *,
    repo_root: Path,
    home: Path,
    max_workers: int = 2,
    registry_path: Path | None = None,
) -> list[str]:
    python = repo_root / ".venv" / "bin" / "python"
    if mode == "parallel":
        if max_workers < 1 or max_workers > 3:
            raise ValueError("max_workers must be in range 1..3")
        registry = registry_path or default_registry_path(home)
        return [
            str(python),
            str(repo_root / "agent_entrypoint.py"),
            "--registry",
            str(registry),
            "--max-workers",
            str(max_workers),
        ]
    if mode == "multirepo":
        return [str(python), str(repo_root / "agent_multirepo.py")]
    if mode == "single":
        return [str(python), str(repo_root / "agentd.py")]
    raise ValueError(f"unsupported launchd mode: {mode!r}")


def build_launch_agent(
    mode: Mode,
    *,
    repo_root: Path,
    home: Path,
    max_workers: int = 2,
    registry_path: Path | None = None,
) -> dict[str, object]:
    repo_root = repo_root.expanduser().resolve()
    home = home.expanduser().resolve()
    logs = home / "Library" / "Logs"
    return {
        "Label": LABEL,
        "ProgramArguments": build_program_arguments(
            mode,
            repo_root=repo_root,
            home=home,
            max_workers=max_workers,
            registry_path=registry_path,
        ),
        "WorkingDirectory": str(repo_root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ProcessType": "Interactive",
        "EnvironmentVariables": {
            "HOME": str(home),
            "PATH": default_path(home),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        "StandardOutPath": str(logs / "local-agent.log"),
        "StandardErrorPath": str(logs / "local-agent-error.log"),
    }


def render_launch_agent(
    mode: Mode,
    *,
    repo_root: Path,
    home: Path,
    max_workers: int = 2,
    registry_path: Path | None = None,
) -> bytes:
    payload = build_launch_agent(
        mode,
        repo_root=repo_root,
        home=home,
        max_workers=max_workers,
        registry_path=registry_path,
    )
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False)


def validate_checkout(repo_root: Path) -> None:
    required = (
        repo_root / ".venv" / "bin" / "python",
        repo_root / "agent_entrypoint.py",
        repo_root / "agent_multirepo.py",
        repo_root / "agentd.py",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("missing Local Agent runtime files: " + ", ".join(missing))


def write_launch_agent(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def launchctl_target(uid: int | None = None) -> str:
    resolved_uid = os.getuid() if uid is None else uid
    return f"gui/{resolved_uid}/{LABEL}"


def launchctl_domain(uid: int | None = None) -> str:
    resolved_uid = os.getuid() if uid is None else uid
    return f"gui/{resolved_uid}"


def bootout(*, uid: int | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", "bootout", launchctl_target(uid)],
        text=True,
        capture_output=True,
        check=check,
    )


def bootstrap(plist_path: Path, *, uid: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", "bootstrap", launchctl_domain(uid), str(plist_path)],
        text=True,
        capture_output=True,
        check=True,
    )


def print_status(*, uid: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", "print", launchctl_target(uid)],
        text=True,
        capture_output=True,
        check=False,
    )
