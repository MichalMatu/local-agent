"""Resolve one operator-selected repository into immutable reasoning-child identity."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from local_agent.development.live_seed import CheckoutIdentity
from local_agent.repository.binding import catalog_record_for_repository
from local_agent.repository.context import RepositoryContext, load_repository_registry

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _git(checkout: Path, *args: str) -> str:
    command = ["git", "-C", str(checkout), *args]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git is required for Conversation Fabric target resolution") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Conversation Fabric target git command timed out: {' '.join(args)}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "git command failed").strip()
        raise RuntimeError(
            f"Conversation Fabric target git command failed ({' '.join(args)}): {detail}"
        ) from exc
    return completed.stdout.strip()


def _canonical_github_repository(remote: str) -> str:
    value = remote.strip()
    if value.startswith("git@github.com:"):
        path = value.removeprefix("git@github.com:")
    else:
        parsed = urlparse(value)
        if parsed.scheme not in {"https", "ssh"} or parsed.hostname != "github.com":
            raise RuntimeError("Conversation Fabric target origin must point to github.com")
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not _REPOSITORY_RE.fullmatch(path):
        raise RuntimeError("Conversation Fabric target origin repository is invalid")
    return path


def resolve_operator_target(
    *,
    home: Path,
    repository_id: str,
    registry_path: Path | None = None,
    catalog_path: Path | None = None,
) -> RepositoryContext:
    """Resolve a target only from enabled runtime registry plus canonical catalog truth."""
    repositories = load_repository_registry(home=home, path=registry_path)
    matches = [
        repository
        for repository in repositories
        if repository.repository_id.casefold() == repository_id.casefold()
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Conversation Fabric target repository is not uniquely enabled: {repository_id!r}"
        )
    target = matches[0]
    record = catalog_record_for_repository(
        target.repository_id,
        target.repository,
        path=catalog_path,
    )
    if not record.execution_enabled:
        raise RuntimeError(
            f"Conversation Fabric target repository is execution-disabled: {target.repository_id!r}"
        )
    if target.agent_binding is None or target.agent_binding != record.agent_binding:
        raise RuntimeError(
            f"Conversation Fabric target binding does not match canonical catalog: "
            f"{target.repository_id!r}"
        )
    return target


def _remote_branch_head(control: Path, branch: str) -> str:
    ref = f"refs/heads/{branch}"
    output = _git(control, "ls-remote", "--exit-code", "origin", ref)
    rows = [line.split() for line in output.splitlines() if line.strip()]
    matches = [row[0] for row in rows if len(row) == 2 and row[1] == ref]
    if len(matches) != 1 or not _SHA_RE.fullmatch(matches[0]):
        raise RuntimeError(
            f"Conversation Fabric target branch does not resolve to one canonical SHA: {branch!r}"
        )
    return matches[0]


def inspect_operator_target(
    *,
    home: Path,
    repository_id: str,
    registry_path: Path | None = None,
    catalog_path: Path | None = None,
    branch_head_provider: Callable[[Path, str], str] = _remote_branch_head,
) -> CheckoutIdentity:
    """Return immutable remote identity without borrowing target execution authority."""
    target = resolve_operator_target(
        home=home,
        repository_id=repository_id,
        registry_path=registry_path,
        catalog_path=catalog_path,
    )
    control = target.control.expanduser().resolve(strict=False)
    if control.is_symlink() or not control.is_dir():
        raise RuntimeError(
            f"Conversation Fabric target control checkout is unavailable or unsafe: {control}"
        )
    top = Path(_git(control, "rev-parse", "--show-toplevel")).resolve(strict=False)
    if top != control:
        raise RuntimeError(
            "Conversation Fabric target control checkout must be the Git worktree root"
        )
    observed_repository = _canonical_github_repository(_git(control, "remote", "get-url", "origin"))
    if observed_repository.casefold() != target.repository.casefold():
        raise RuntimeError(
            "Conversation Fabric target origin does not match runtime registry identity"
        )
    sha = branch_head_provider(control, target.default_branch)
    if not _SHA_RE.fullmatch(sha):
        raise RuntimeError("Conversation Fabric target branch head must be a canonical commit SHA")
    return CheckoutIdentity(
        repository_id=target.repository_id,
        repository=target.repository,
        agent_binding=str(target.agent_binding),
        repository_ref=target.default_branch,
        repository_commit_sha=sha,
    )
