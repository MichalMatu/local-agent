#!/usr/bin/env python3
"""Root import surface for repository hard-binding contracts."""

from local_agent.repository.binding import (
    CATALOG_VERSION,
    CONTROL_BINDING_RELATIVE,
    CONTROL_BINDING_VERSION,
    DEFAULT_CATALOG_PATH,
    AgentBindingRecord,
    apply_catalog_to_registry_payload,
    canonical_agent_binding,
    catalog_record_for_repository,
    control_binding_payload,
    load_binding_catalog,
    validate_repository_control_binding,
)

__all__ = [
    "CATALOG_VERSION",
    "CONTROL_BINDING_RELATIVE",
    "CONTROL_BINDING_VERSION",
    "DEFAULT_CATALOG_PATH",
    "AgentBindingRecord",
    "apply_catalog_to_registry_payload",
    "canonical_agent_binding",
    "catalog_record_for_repository",
    "control_binding_payload",
    "load_binding_catalog",
    "validate_repository_control_binding",
]
