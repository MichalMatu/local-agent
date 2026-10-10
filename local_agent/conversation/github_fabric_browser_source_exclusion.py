"""Bounded, offline source audit for the non-authoritative Chrome driver.

This is a regression alarm for production source imports, not a browser
admission check. It cannot inventory, revoke or exclude old/offline clients.
Every outcome continues to forbid GitHub-first browser Send/ACK.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_MAX_FILE_BYTES = 256 * 1024
_MAX_SCRIPT_COUNT = 64
_NAME = re.compile(r"[a-z][a-z0-9_]*\.js\Z")
_IMPORT = re.compile(r"\s*importScripts\((?P<names>.*?)\);\s*\Z", re.DOTALL)
_QUOTED_NAME = re.compile(r'"([a-z][a-z0-9_]*\.js)"')
_PRIVATE = re.compile(r"github_fabric_private_[a-z0-9_]+")
_UNAPPROVED_LOADER = re.compile(
    r"\b(?:importScripts|eval|require)\s*\(|\bimport\s*\(|\bnew\s+Function\s*\("
)


@dataclass(frozen=True, slots=True)
class BrowserSourceExclusionAudit:
    inspected_scripts: tuple[str, ...]
    decision: str = "blocked_unattested_legacy_clients"
    browser_effects_permitted: bool = False
    old_offline_clients_excluded: bool = False
    independent_review_completed: bool = False


def _read_text(directory: Path, name: str) -> str:
    if _NAME.fullmatch(name) is None:
        raise ValueError("Browser source path is not a bounded JavaScript basename")
    path = directory / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_FILE_BYTES:
        raise ValueError("Browser source file absent, linked or oversized")
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Browser source is not UTF-8") from None


def _worker_imports(source: str) -> tuple[str, ...]:
    """Require one completely static, quoted bootstrap importScripts statement."""
    match = _IMPORT.fullmatch(source)
    if match is None:
        raise ValueError("Browser bootstrap import graph is not statically enumerable")
    names = tuple(_QUOTED_NAME.findall(match["names"]))
    remainder = _QUOTED_NAME.sub("S", match["names"])
    if (
        not names or len(names) > _MAX_SCRIPT_COUNT or len(names) != len(set(names))
        or re.fullmatch(r"\s*S(?:\s*,\s*S)*\s*", remainder) is None
    ):
        raise ValueError("Browser bootstrap has ambiguous or duplicate imports")
    return names


def _script_safety(name: str, source: str) -> None:
    if _PRIVATE.search(source):
        raise ValueError("Private GitHub Fabric module referenced by production source")
    if name != "service_worker.js" and _UNAPPROVED_LOADER.search(source):
        raise ValueError("Browser source has an unreviewed secondary code loader")


def audit_browser_source_exclusion(repo_root: Path) -> BrowserSourceExclusionAudit:
    """Inspect the checked-in source graph; NEVER issue effect authorization."""
    root = repo_root / "chat_bridge"
    manifest_path = root / "manifest.json"
    if (
        manifest_path.is_symlink() or not manifest_path.is_file()
        or manifest_path.stat().st_size > _MAX_FILE_BYTES
    ):
        raise ValueError("Browser extension manifest missing or oversized")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("Browser extension manifest invalid") from None
    if (
        type(manifest) is not dict or type(manifest.get("background")) is not dict
        or manifest["background"].get("service_worker") != "service_worker.js"
        or type(manifest.get("content_scripts")) is not list
        or not 1 <= len(manifest["content_scripts"]) <= 8
    ):
        raise ValueError("Browser extension startup graph invalid")
    worker = _read_text(root, "service_worker.js")
    worker_names = _worker_imports(worker)
    content_names: list[str] = []
    for entry in manifest["content_scripts"]:
        if type(entry) is not dict or type(entry.get("js")) is not list:
            raise ValueError("Browser content script list invalid")
        content_names.extend(entry["js"])
    names = ("service_worker.js", *worker_names, *content_names)
    if len(names) > _MAX_SCRIPT_COUNT or any(
        type(name) is not str or _NAME.fullmatch(name) is None for name in names
    ):
        raise ValueError("Browser production script graph exceeds bound")
    # A shared source may legitimately load once in each execution realm.
    # Duplicate imports *within* one realm remain ambiguous and denied.
    if len(content_names) != len(set(content_names)):
        raise ValueError("Browser content script identity duplicated")
    sources = {name: _read_text(root, name) for name in names}
    for name, source in sources.items():
        _script_safety(name, source)

    # Presence of old browser effect entry points is a *blocker*, not proof
    # that those entry points or unknown offline copies have been retired.
    if (
        "worker_conversation_fabric.js" not in worker_names
        or "worker_spawn.js" not in worker_names
        or "content.js" not in content_names
        or "chrome.tabs.create(" not in sources["worker_spawn.js"]
        or "sendButton.click()" not in sources["content.js"]
    ):
        raise ValueError("Legacy browser effect inventory changed; renew review")
    intake = sources.get("worker_github_fabric_intake.js")
    if (
        intake is None or "runtime.githubFabricReadOnlyIntakeEnabled !== true" not in intake
        or re.search(r"\bchrome\.(?:tabs|scripting)\.", intake)
        or re.search(
            r"\b(?:createConversationSpawnTab|submitConversationSpawnBootstrap"
            r"|createConversationFabricCampaign)\s*\(", intake
        )
    ):
        raise ValueError("GitHub-first observation-only intake changed")
    return BrowserSourceExclusionAudit(inspected_scripts=tuple(sorted(sources)))
