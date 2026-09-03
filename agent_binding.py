#!/usr/bin/env python3
"""Canonical opaque agent-binding identities shared by bridge and executor."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATALOG_VERSION = 1
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent / "config" / "agent_bindings.json"


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
