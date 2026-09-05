"""Canonical opaque agent-binding identities shared by bridge and executor."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATALOG_VERSION = 1
CONTROL_BINDING_VERSION = 1
CONTROL_BINDING_RELATIVE = ".agent/binding.json"
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "config" / "agent_bindings.json"


@dataclass(frozen=True, slots=True)
class AgentBindingRecord:
    repository_id: str
    repository: str
    agent_binding: str
    execution_enabled: bool


def canonical_agent_binding(value: Any, *, field: str = "agent_binding") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a canonical UUID string")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{field} must be a canonical UUID string") from exc
    canonical = str(parsed)
    if value != canonical:
        raise ValueError(f"{field} must use canonical lowercase UUID form")
    return canonical


def load_binding_catalog(path: Path | None = None) -> list[AgentBindingRecord]:
    catalog_path = path or DEFAULT_CATALOG_PATH
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != CATALOG_VERSION:
        raise ValueError(f"unsupported agent binding catalog: {catalog_path}")
    raw_agents = payload.get("agents")
    if not isinstance(raw_agents, list):
        raise ValueError("agent binding catalog agents must be a list")

    records: list[AgentBindingRecord] = []
    ids: set[str] = set()
    repositories: set[str] = set()
    bindings: set[str] = set()
    for item in raw_agents:
        if not isinstance(item, dict):
            raise ValueError("agent binding catalog entries must be objects")
        repository_id = item.get("id")
        repository = item.get("repository")
        execution_enabled = item.get("execution_enabled", True)
        if not isinstance(repository_id, str) or not repository_id:
            raise ValueError("agent binding catalog id must be a non-empty string")
        if not isinstance(repository, str) or "/" not in repository:
            raise ValueError("agent binding catalog repository must be owner/name")
        if not isinstance(execution_enabled, bool):
            raise ValueError("execution_enabled must be a boolean")
        binding = canonical_agent_binding(item.get("agent_binding"))
        id_key = repository_id.casefold()
        repo_key = repository.casefold()
        if id_key in ids:
            raise ValueError(f"duplicate agent binding id: {repository_id!r}")
        if repo_key in repositories:
            raise ValueError(f"duplicate agent binding repository: {repository!r}")
        if binding in bindings:
            raise ValueError(f"duplicate agent binding UUID: {binding}")
        ids.add(id_key)
        repositories.add(repo_key)
        bindings.add(binding)
        records.append(
            AgentBindingRecord(
                repository_id=repository_id,
                repository=repository,
                agent_binding=binding,
                execution_enabled=execution_enabled,
            )
        )
    return records


def catalog_record_for_repository(
    repository_id: str,
    repository: str,
    *,
    path: Path | None = None,
) -> AgentBindingRecord:
    for record in load_binding_catalog(path):
        if (
            record.repository_id.casefold() == repository_id.casefold()
            and record.repository.casefold() == repository.casefold()
        ):
            return record
    raise ValueError(
        f"no canonical agent binding for repository id={repository_id!r} repository={repository!r}"
    )


def control_binding_payload(control_dir: Path) -> dict[str, Any]:
    path = control_dir / CONTROL_BINDING_RELATIVE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"repository control binding is missing: {path}") from exc
    if not isinstance(payload, dict) or payload.get("version") != CONTROL_BINDING_VERSION:
        raise ValueError(f"invalid repository control binding: {path}")
    return payload


def validate_repository_control_binding(
    *,
    repository_id: str,
    repository: str,
    expected_agent_binding: str,
    control_dir: Path,
) -> str:
    expected = canonical_agent_binding(expected_agent_binding, field="expected_agent_binding")
    payload = control_binding_payload(control_dir)
    actual_id = payload.get("repository_id")
    actual_repository = payload.get("repository")
    actual_binding = canonical_agent_binding(payload.get("agent_binding"))
    if actual_id != repository_id:
        raise ValueError(
            f"control binding repository id mismatch: expected {repository_id!r}, got {actual_id!r}"
        )
    if not isinstance(actual_repository, str) or actual_repository.casefold() != repository.casefold():
        raise ValueError(
            f"control binding repository mismatch: expected {repository!r}, got {actual_repository!r}"
        )
    if actual_binding != expected:
        raise ValueError(
            f"control binding UUID mismatch: expected {expected}, got {actual_binding}"
        )
    return actual_binding


def apply_catalog_to_registry_payload(
    payload: dict[str, Any],
    *,
    catalog_path: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Return a registry payload with canonical bindings applied by id+repository identity."""
    if not isinstance(payload, dict) or not isinstance(payload.get("repositories"), list):
        raise ValueError("repository registry must contain a repositories list")
    catalog = load_binding_catalog(catalog_path)
    records = {
        (record.repository_id.casefold(), record.repository.casefold()): record
        for record in catalog
        if record.execution_enabled
    }
    result = json.loads(json.dumps(payload))
    changes: list[dict[str, str]] = []
    for item in result["repositories"]:
        if not isinstance(item, dict):
            raise ValueError("repository registry entries must be objects")
        if item.get("enabled", True) is False:
            continue
        repository_id = item.get("id")
        repository = item.get("repository")
        if not isinstance(repository_id, str) or not isinstance(repository, str):
            raise ValueError("repository registry entry identity is invalid")
        record = records.get((repository_id.casefold(), repository.casefold()))
        if record is None:
            raise ValueError(
                f"no execution binding catalog entry for {repository_id!r} {repository!r}"
            )
        previous = item.get("agent_binding")
        if previous is not None and canonical_agent_binding(previous) != record.agent_binding:
            raise ValueError(
                f"registry binding differs from canonical catalog for {repository_id!r}"
            )
        item["agent_binding"] = record.agent_binding
        if previous != record.agent_binding:
            changes.append(
                {
                    "repository_id": repository_id,
                    "repository": repository,
                    "agent_binding": record.agent_binding,
                }
            )
    return result, changes
