from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from local_agent.conversation import contract
from local_agent.repository.binding import canonical_agent_binding

CHILD_CHECKPOINT_SCHEMA_VERSION = 1
CHILD_TERMINAL_SCHEMA_VERSION = 1
MAX_CHECKPOINT_BYTES = 16 * 1024
MAX_TERMINAL_BYTES = 32 * 1024
MAX_CHECKPOINTS = 128
MAX_SUMMARY_CHARS = 8192
MAX_EVIDENCE_REFS = 32
MAX_TASK_ID_CHARS = 200
MAX_REPOSITORY_NAME_CHARS = 200
MAX_GITHUB_RUN_ID = 2**63 - 1
MAX_GITHUB_RUN_ATTEMPT = 2**31 - 1

TERMINAL_OUTCOMES = frozenset({"succeeded", "failed"})
EVIDENCE_KINDS = frozenset(
    {
        "git_commit",
        "local_agent_task_result",
        "github_actions_run",
    }
)

_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_REPOSITORY_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
_GITHUB_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PREFIXED_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_PROVENANCE_FIELDS = frozenset(
    {
        "child_request_id",
        "child_request_digest",
        "workflow_id",
        "workflow_node_id",
        "workflow_node_revision",
        "workflow_node_introduction_digest",
    }
)


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
        raise ValueError("conversation evidence record must be canonical JSON data") from exc
    return text.encode("utf-8")


def _validate_exact_fields(
    payload: dict[str, Any], *, fields: frozenset[str], label: str
) -> None:
    extra = set(payload) - fields
    if extra:
        raise ValueError(f"{label} contains unsupported fields: {sorted(extra)!r}")
    missing = fields - set(payload)
    if missing:
        raise ValueError(f"{label} is missing required fields: {sorted(missing)!r}")


def _validate_id(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > contract.MAX_ID_CHARS
        or value != value.strip()
        or not _ID_RE.fullmatch(value)
    ):
        raise ValueError(f"{field} must be a bounded canonical identifier")
    return value


def _validate_timestamp(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z") or len(value) > 64:
        raise ValueError(f"{field} must be a bounded RFC3339 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid RFC3339 UTC timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{field} must use UTC")
    return value


def _validate_summary(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > MAX_SUMMARY_CHARS
    ):
        raise ValueError(f"{field} must be a non-empty bounded string")
    return value


def _validate_repository_id(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _REPOSITORY_ID_RE.fullmatch(value):
        raise ValueError(f"{field} must be a bounded canonical repository id")
    return value


def _validate_task_id(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_TASK_ID_CHARS
        or not _TASK_ID_RE.fullmatch(value)
    ):
        raise ValueError("evidence task_id must be a bounded canonical task id")
    return value


def _validate_positive_int(value: Any, *, field: str, maximum: int) -> int:
    if type(value) is not int or value < 1 or value > maximum:
        raise ValueError(f"{field} must be 1..{maximum}")
    return value


def _validate_git_commit_ref(reference: dict[str, Any]) -> None:
    fields = frozenset({"kind", "repository_id", "commit_sha"})
    _validate_exact_fields(reference, fields=fields, label="git_commit evidence reference")
    _validate_repository_id(reference.get("repository_id"), field="evidence repository_id")
    commit_sha = reference.get("commit_sha")
    if not isinstance(commit_sha, str) or not _COMMIT_SHA_RE.fullmatch(commit_sha):
        raise ValueError("git_commit evidence commit_sha must be an exact lowercase 40-character SHA")


def _validate_local_agent_result_ref(reference: dict[str, Any]) -> None:
    fields = frozenset(
        {
            "kind",
            "repository_id",
            "agent_binding",
            "task_id",
            "task_digest",
        }
    )
    _validate_exact_fields(
        reference,
        fields=fields,
        label="local_agent_task_result evidence reference",
    )
    _validate_repository_id(reference.get("repository_id"), field="evidence repository_id")
    canonical_agent_binding(reference.get("agent_binding"), field="evidence agent_binding")
    _validate_task_id(reference.get("task_id"))
    digest = reference.get("task_digest")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise ValueError("local_agent_task_result task_digest must be an exact lowercase sha256")


def _validate_github_actions_ref(reference: dict[str, Any]) -> None:
    fields = frozenset(
        {
            "kind",
            "repository",
            "run_id",
            "run_attempt",
            "head_sha",
        }
    )
    _validate_exact_fields(
        reference,
        fields=fields,
        label="github_actions_run evidence reference",
    )
    repository = reference.get("repository")
    if (
        not isinstance(repository, str)
        or len(repository) > MAX_REPOSITORY_NAME_CHARS
        or not _GITHUB_REPOSITORY_RE.fullmatch(repository)
    ):
        raise ValueError("github_actions_run repository must use canonical owner/name form")
    _validate_positive_int(
        reference.get("run_id"),
        field="github_actions_run run_id",
        maximum=MAX_GITHUB_RUN_ID,
    )
    _validate_positive_int(
        reference.get("run_attempt"),
        field="github_actions_run run_attempt",
        maximum=MAX_GITHUB_RUN_ATTEMPT,
    )
    head_sha = reference.get("head_sha")
    if not isinstance(head_sha, str) or not _COMMIT_SHA_RE.fullmatch(head_sha):
        raise ValueError("github_actions_run head_sha must be an exact lowercase 40-character SHA")


def validate_evidence_ref(reference: Any) -> None:
    if not isinstance(reference, dict):
        raise ValueError("evidence reference must be an object")
    kind = reference.get("kind")
    if not isinstance(kind, str) or kind not in EVIDENCE_KINDS:
        raise ValueError(f"unsupported evidence reference kind: {kind!r}")
    if kind == "git_commit":
        _validate_git_commit_ref(reference)
    elif kind == "local_agent_task_result":
        _validate_local_agent_result_ref(reference)
    elif kind == "github_actions_run":
        _validate_github_actions_ref(reference)


def _validate_evidence_refs(value: Any) -> None:
    if not isinstance(value, list):
        raise ValueError("evidence_refs must be a list")
    if len(value) > MAX_EVIDENCE_REFS:
        raise ValueError(f"evidence_refs exceeds {MAX_EVIDENCE_REFS} items")
    seen: set[bytes] = set()
    for reference in value:
        validate_evidence_ref(reference)
        identity = _canonical_bytes(reference)
        if identity in seen:
            raise ValueError("evidence_refs must not contain duplicates")
        seen.add(identity)


def _validate_provenance(record: dict[str, Any], request: dict[str, Any] | None) -> None:
    _validate_id(record.get("child_request_id"), field="child_request_id")
    digest = record.get("child_request_digest")
    if not isinstance(digest, str) or not _PREFIXED_SHA256_RE.fullmatch(digest):
        raise ValueError("child_request_digest must be a canonical sha256 digest")
    _validate_id(record.get("workflow_id"), field="workflow_id")
    _validate_id(record.get("workflow_node_id"), field="workflow_node_id")
    revision = record.get("workflow_node_revision")
    if type(revision) is not int or revision < 0 or revision > 2**31 - 1:
        raise ValueError("workflow_node_revision must be a bounded non-negative integer")
    introduction_digest = record.get("workflow_node_introduction_digest")
    if (
        not isinstance(introduction_digest, str)
        or not _PREFIXED_SHA256_RE.fullmatch(introduction_digest)
    ):
        raise ValueError("workflow_node_introduction_digest must be a canonical sha256 digest")

    if request is None:
        return
    contract.validate_child_request(request)
    expected = {
        "child_request_id": request["id"],
        "child_request_digest": contract.child_request_digest(request),
        "workflow_id": request["workflow_id"],
        "workflow_node_id": request["workflow_node_id"],
        "workflow_node_revision": request["workflow_node_revision"],
        "workflow_node_introduction_digest": request["workflow_node_introduction_digest"],
    }
    for field in _PROVENANCE_FIELDS:
        actual = record[field]
        wanted = expected[field]
        if isinstance(actual, str) and isinstance(wanted, str):
            if not secrets.compare_digest(actual, wanted):
                raise ValueError(f"conversation evidence {field} does not match child request")
        elif actual != wanted:
            raise ValueError(f"conversation evidence {field} does not match child request")


def validate_child_checkpoint(
    checkpoint: dict[str, Any], *, request: dict[str, Any] | None = None
) -> None:
    if not isinstance(checkpoint, dict):
        raise ValueError("child checkpoint must be an object")
    if len(_canonical_bytes(checkpoint)) > MAX_CHECKPOINT_BYTES:
        raise ValueError(f"child checkpoint exceeds {MAX_CHECKPOINT_BYTES} bytes")
    fields = frozenset(
        {
            "schema_version",
            *_PROVENANCE_FIELDS,
            "sequence",
            "summary",
            "evidence_refs",
            "recorded_at",
        }
    )
    _validate_exact_fields(checkpoint, fields=fields, label="child checkpoint")
    if (
        type(checkpoint.get("schema_version")) is not int
        or checkpoint["schema_version"] != CHILD_CHECKPOINT_SCHEMA_VERSION
    ):
        raise ValueError(
            f"child checkpoint schema_version must be {CHILD_CHECKPOINT_SCHEMA_VERSION}"
        )
    _validate_provenance(checkpoint, request)
    _validate_positive_int(
        checkpoint.get("sequence"),
        field="child checkpoint sequence",
        maximum=MAX_CHECKPOINTS,
    )
    _validate_summary(checkpoint.get("summary"), field="child checkpoint summary")
    _validate_evidence_refs(checkpoint.get("evidence_refs"))
    _validate_timestamp(checkpoint.get("recorded_at"), field="child checkpoint recorded_at")


def validate_child_terminal(
    terminal: dict[str, Any], *, request: dict[str, Any] | None = None
) -> None:
    if not isinstance(terminal, dict):
        raise ValueError("child terminal must be an object")
    if len(_canonical_bytes(terminal)) > MAX_TERMINAL_BYTES:
        raise ValueError(f"child terminal exceeds {MAX_TERMINAL_BYTES} bytes")
    fields = frozenset(
        {
            "schema_version",
            *_PROVENANCE_FIELDS,
            "outcome",
            "summary",
            "evidence_refs",
            "recorded_at",
        }
    )
    _validate_exact_fields(terminal, fields=fields, label="child terminal")
    if (
        type(terminal.get("schema_version")) is not int
        or terminal["schema_version"] != CHILD_TERMINAL_SCHEMA_VERSION
    ):
        raise ValueError(
            f"child terminal schema_version must be {CHILD_TERMINAL_SCHEMA_VERSION}"
        )
    _validate_provenance(terminal, request)
    outcome = terminal.get("outcome")
    if not isinstance(outcome, str) or outcome not in TERMINAL_OUTCOMES:
        raise ValueError(f"child terminal outcome must be one of {sorted(TERMINAL_OUTCOMES)!r}")
    _validate_summary(terminal.get("summary"), field="child terminal summary")
    _validate_evidence_refs(terminal.get("evidence_refs"))
    _validate_timestamp(terminal.get("recorded_at"), field="child terminal recorded_at")


def _semantic_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "recorded_at"}


def child_checkpoint_digest(
    checkpoint: dict[str, Any], *, request: dict[str, Any] | None = None
) -> str:
    validate_child_checkpoint(checkpoint, request=request)
    return "sha256:" + hashlib.sha256(_canonical_bytes(_semantic_payload(checkpoint))).hexdigest()


def child_terminal_digest(
    terminal: dict[str, Any], *, request: dict[str, Any] | None = None
) -> str:
    validate_child_terminal(terminal, request=request)
    return "sha256:" + hashlib.sha256(_canonical_bytes(_semantic_payload(terminal))).hexdigest()
