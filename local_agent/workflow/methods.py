from __future__ import annotations

import hashlib
import json
import re
from typing import Any

METHOD_SCHEMA_VERSION = 1
MAX_METHOD_FILE_BYTES = 256 * 1024
MAX_METHOD_NAME_CHARS = 100
MAX_METHOD_DESCRIPTION_CHARS = 4096
MAX_METHOD_PHASES = 32
MAX_METHOD_REQUIREMENTS = 64

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical_bytes(payload: Any) -> bytes:
    try:
        text = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("method payload must be canonical JSON data") from exc
    return text.encode("utf-8")


def _canonical_name(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_METHOD_NAME_CHARS:
        raise ValueError(f"{field} must be a non-empty bounded string")
    if value != value.strip() or value != value.casefold() or not _NAME_RE.fullmatch(value):
        raise ValueError(f"{field} must be canonical lowercase text")
    return value


def validate_method_spec(spec: dict[str, Any]) -> None:
    if not isinstance(spec, dict):
        raise ValueError("method spec must be an object")
    if len(_canonical_bytes(spec)) > MAX_METHOD_FILE_BYTES:
        raise ValueError(f"method spec exceeds {MAX_METHOD_FILE_BYTES} bytes")

    allowed = {
        "schema_version",
        "name",
        "version",
        "description",
        "required_phases",
        "requirements",
    }
    extra = set(spec) - allowed
    if extra:
        raise ValueError(f"method spec contains unsupported fields: {sorted(extra)!r}")

    if type(spec.get("schema_version")) is not int or spec["schema_version"] != METHOD_SCHEMA_VERSION:
        raise ValueError(f"method schema_version must be {METHOD_SCHEMA_VERSION}")
    _canonical_name(spec.get("name"), field="method name")

    version = spec.get("version")
    if type(version) is not int or version < 1:
        raise ValueError("method version must be a positive integer")

    description = spec.get("description")
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > MAX_METHOD_DESCRIPTION_CHARS
    ):
        raise ValueError("method description must be a non-empty bounded string")

    phases = spec.get("required_phases")
    if not isinstance(phases, list) or not phases:
        raise ValueError("required_phases must be a non-empty list")
    if len(phases) > MAX_METHOD_PHASES:
        raise ValueError(f"required_phases exceeds {MAX_METHOD_PHASES} items")
    seen: set[str] = set()
    for phase in phases:
        normalized = _canonical_name(phase, field="required phase")
        if normalized in seen:
            raise ValueError(f"duplicate required phase: {normalized!r}")
        seen.add(normalized)

    requirements = spec.get("requirements")
    if not isinstance(requirements, dict):
        raise ValueError("requirements must be an object")
    if len(requirements) > MAX_METHOD_REQUIREMENTS:
        raise ValueError(f"requirements exceeds {MAX_METHOD_REQUIREMENTS} items")
    for key, value in requirements.items():
        _canonical_name(key, field="requirement name")
        if not isinstance(value, bool):
            raise ValueError("requirement values must be booleans")


def method_digest(spec: dict[str, Any]) -> str:
    validate_method_spec(spec)
    return "sha256:" + hashlib.sha256(_canonical_bytes(spec)).hexdigest()


def validate_method_reference(reference: dict[str, Any]) -> None:
    if not isinstance(reference, dict):
        raise ValueError("method reference must be an object")
    if set(reference) != {"name", "version", "digest"}:
        raise ValueError("method reference must contain exactly name, version, and digest")
    _canonical_name(reference.get("name"), field="method reference name")
    version = reference.get("version")
    if type(version) is not int or version < 1:
        raise ValueError("method reference version must be a positive integer")
    digest = reference.get("digest")
    if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
        raise ValueError("method reference digest must be sha256:<64 lowercase hex chars>")


def require_method_match(reference: dict[str, Any], spec: dict[str, Any]) -> None:
    validate_method_reference(reference)
    validate_method_spec(spec)
    if reference["name"] != spec["name"] or reference["version"] != spec["version"]:
        raise ValueError("method reference identity does not match method spec")
    actual = method_digest(spec)
    if reference["digest"] != actual:
        raise ValueError(
            f"method reference digest mismatch: expected {actual}, got {reference['digest']}"
        )
