"""Repository registry, workspace identity and execution lease identities."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from local_agent.repository.binding import canonical_agent_binding

DEFAULT_REPOSITORY_ID = "litegraph"
DEFAULT_REPOSITORY = "MichalMatu/esp32s3_LiteGraph"
DEFAULT_CONTROL_BRANCH = "agent-control"
DEFAULT_SOURCE_BRANCH = "main"
REGISTRY_VERSION = 1

_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


@dataclass(frozen=True, slots=True)
class RepositoryContext:
    repository_id: str
    repository: str
    control: Path
    work: Path
    checkpoints: Path
    control_branch: str = DEFAULT_CONTROL_BRANCH
    default_branch: str = DEFAULT_SOURCE_BRANCH
    agent_binding: str | None = None

    def status_fields(self) -> dict[str, str]:
        return {
            "repository_id": self.repository_id,
            "repository": self.repository,
            "control_branch": self.control_branch,
            "default_branch": self.default_branch,
            "agent_binding": self.agent_binding or "unbound",
        }


def default_registry_path(home: Path) -> Path:
    return home / "Library" / "Application Support" / "local-agent" / "repositories.json"


def legacy_repository(home: Path) -> RepositoryContext:
    root = home / "agent-workspace"
    return RepositoryContext(
        repository_id=DEFAULT_REPOSITORY_ID,
        repository=DEFAULT_REPOSITORY,
        control=root / "control",
        work=root / "work",
        checkpoints=root / "checkpoints",
        agent_binding=None,
    )


def _validate_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid repository id: {value!r}")
    repository_id = value
    if not _ID_RE.fullmatch(repository_id):
        raise ValueError(f"invalid repository id: {repository_id!r}")
    return repository_id


def _validate_repository(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid repository name: {value!r}")
    repository = value
    if not _REPOSITORY_RE.fullmatch(repository):
        raise ValueError(f"invalid repository name: {repository!r}")
    return repository


def _validate_branch(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid {field}: {value!r}")
    branch = value
    if (
        not branch
        or not _BRANCH_RE.fullmatch(branch)
        or ".." in branch
        or branch.startswith("/")
        or branch.endswith("/")
    ):
        raise ValueError(f"invalid {field}: {branch!r}")
    return branch


def _absolute_path(value: Any, *, home: Path, default: Path) -> Path:
    if value is None:
        path = default
    else:
        if not isinstance(value, str):
            raise ValueError(f"repository workspace path must be a string: {value!r}")
        raw = value
        if raw.startswith("~/"):
            path = home / raw[2:]
        else:
            path = Path(raw)
    if not path.is_absolute():
        raise ValueError(f"repository workspace path must be absolute: {path}")
    return path.resolve(strict=False)


def repository_from_dict(item: dict[str, Any], *, home: Path) -> RepositoryContext:
    repository_id = _validate_id(item.get("id"))
    repository = _validate_repository(item.get("repository"))
    control_branch = _validate_branch(
        item.get("control_branch", DEFAULT_CONTROL_BRANCH),
        "control_branch",
    )
    default_branch = _validate_branch(
        item.get("default_branch", DEFAULT_SOURCE_BRANCH),
        "default_branch",
    )
    raw_binding = item.get("agent_binding")
    agent_binding = (
        None
        if raw_binding is None
        else canonical_agent_binding(raw_binding, field=f"{repository_id}.agent_binding")
    )

    legacy_workspace = item.get("legacy_workspace", False)
    if not isinstance(legacy_workspace, bool):
        raise ValueError("legacy_workspace must be a boolean")
    if legacy_workspace:
        defaults = legacy_repository(home)
        default_control = defaults.control
        default_work = defaults.work
        default_checkpoints = defaults.checkpoints
    else:
        root = home / "agent-workspace" / "repos" / repository_id
        default_control = root / "control"
        default_work = root / "work"
        default_checkpoints = root / "checkpoints"

    return RepositoryContext(
        repository_id=repository_id,
        repository=repository,
        control=_absolute_path(item.get("control_dir"), home=home, default=default_control),
        work=_absolute_path(item.get("work_dir"), home=home, default=default_work),
        checkpoints=_absolute_path(
            item.get("checkpoints_dir"),
            home=home,
            default=default_checkpoints,
        ),
        control_branch=control_branch,
        default_branch=default_branch,
        agent_binding=agent_binding,
    )


def _normalized_path_identity(path: Path) -> str:
    resolved = path.resolve(strict=False)
    return unicodedata.normalize("NFC", str(resolved)).casefold()


def _paths_overlap(first: Path, second: Path) -> bool:
    first_identity = Path(_normalized_path_identity(first))
    second_identity = Path(_normalized_path_identity(second))
    if (
        first_identity == second_identity
        or first_identity in second_identity.parents
        or second_identity in first_identity.parents
    ):
        return True
    try:
        return first.exists() and second.exists() and first.samefile(second)
    except OSError:
        return False


def repository_config_digest(repository: RepositoryContext) -> str:
    """Return an immutable worker-dispatch identity for one registry entry."""
    payload = {
        "repository_id": repository.repository_id,
        "repository": repository.repository,
        "control": str(repository.control),
        "work": str(repository.work),
        "checkpoints": str(repository.checkpoints),
        "control_branch": repository.control_branch,
        "default_branch": repository.default_branch,
        "agent_binding": repository.agent_binding,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def repository_lease_keys(repository: RepositoryContext) -> tuple[str, ...]:
    """Return repository and resource identities for execution exclusion."""
    keys = (
        f"id:{repository.repository_id.casefold()}",
        f"remote:{repository.repository.casefold()}",
        f"control:{_normalized_path_identity(repository.control)}",
        f"work:{_normalized_path_identity(repository.work)}",
        f"checkpoints:{_normalized_path_identity(repository.checkpoints)}",
    )
    return tuple(sorted(keys))


def validate_repository_set(repositories: Iterable[RepositoryContext]) -> list[RepositoryContext]:
    result = list(repositories)
    if not result:
        raise ValueError("repository registry must contain at least one repository")

    ids: dict[str, str] = {}
    remotes: dict[str, str] = {}
    bindings: dict[str, str] = {}
    paths: dict[Path, tuple[str, str]] = {}
    for repository in result:
        normalized_id = repository.repository_id.casefold()
        if normalized_id in ids:
            raise ValueError(f"duplicate repository id: {repository.repository_id!r}")
        ids[normalized_id] = repository.repository_id
        normalized_remote = repository.repository.casefold()
        if normalized_remote in remotes:
            raise ValueError(
                f"duplicate remote repository: {repository.repository!r} "
                f"also configured by {remotes[normalized_remote]!r}"
            )
        remotes[normalized_remote] = repository.repository_id
        if repository.agent_binding is not None:
            if repository.agent_binding in bindings:
                raise ValueError(
                    f"duplicate agent binding: {repository.agent_binding} "
                    f"also configured by {bindings[repository.agent_binding]!r}"
                )
            bindings[repository.agent_binding] = repository.repository_id
        for field, path in (
            ("control", repository.control),
            ("work", repository.work),
            ("checkpoints", repository.checkpoints),
        ):
            for previous_path, (other_id, other_field) in paths.items():
                if _paths_overlap(path, previous_path):
                    raise ValueError(
                        f"workspace path collision: {repository.repository_id}.{field} "
                        f"at {path} overlaps {other_id}.{other_field} at {previous_path}"
                    )
            paths[path] = (repository.repository_id, field)
    return result


def repository_by_binding(
    repositories: Iterable[RepositoryContext],
    agent_binding: str,
) -> RepositoryContext:
    binding = canonical_agent_binding(agent_binding)
    matches = [repository for repository in repositories if repository.agent_binding == binding]
    if not matches:
        raise ValueError(f"agent binding is not enabled: {binding}")
    if len(matches) != 1:
        raise ValueError(f"agent binding is ambiguous: {binding}")
    return matches[0]


def load_repository_registry(
    *,
    home: Path | None = None,
    path: Path | None = None,
) -> list[RepositoryContext]:
    resolved_home = (home or Path.home()).resolve()
    registry_path = path or default_registry_path(resolved_home)
    if not registry_path.exists():
        return [legacy_repository(resolved_home)]

    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("repository registry root must be an object")
    version = payload.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version != REGISTRY_VERSION:
        raise ValueError(
            f"unsupported repository registry version: {payload.get('version')!r}"
        )
    raw_repositories = payload.get("repositories")
    if not isinstance(raw_repositories, list):
        raise ValueError("repository registry repositories must be a list")

    repositories: list[RepositoryContext] = []
    for item in raw_repositories:
        if not isinstance(item, dict):
            raise ValueError("repository registry entries must be objects")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("repository enabled must be a boolean")
        if not enabled:
            continue
        repositories.append(repository_from_dict(item, home=resolved_home))
    return validate_repository_set(repositories)
