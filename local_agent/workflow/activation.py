from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_agent.foundation.process import fsync_directory
from local_agent.workflow import continuation, revisions, state
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore

ACTIVATION_SCHEMA_VERSION = 1
MAX_ACTIVATION_FILE_BYTES = 1024 * 1024
ACTIVATION_FILENAME_WIDTH = 6
MAX_ACTIVATION_ID_CHARS = 200
MAX_RESOLVER_CHARS = 200
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

_ACTIVATION_FIELDS = {
    "schema_version",
    "workflow_id",
    "revision",
    "revision_digest",
    "parent_tip_digest",
    "checkpoint_node_id",
    "checkpoint_resolution_digest",
    "prior_state_digest",
    "new_node_states",
    "activated_at",
}


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
        raise ValueError("workflow activation payload must be canonical JSON data") from exc
    return text.encode("utf-8")


def canonical_digest(payload: Any) -> str:
    encoded = _canonical_bytes(payload)
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _validate_timestamp(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{field} must use UTC")
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_canonical_id(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_ACTIVATION_ID_CHARS
        or not _ID_RE.fullmatch(value)
    ):
        raise ValueError(f"{field} must be a bounded canonical identifier")
    return value


def _validate_checkpoint_resolution(
    resolution: dict[str, Any],
    *,
    workflow_id: str,
    checkpoint_node_id: str,
) -> None:
    if not isinstance(resolution, dict):
        raise ValueError("checkpoint resolution provenance must be an object")
    if resolution.get("workflow_id") != workflow_id:
        raise ValueError("checkpoint resolution workflow identity mismatch")
    if resolution.get("node_id") != checkpoint_node_id:
        raise ValueError("checkpoint resolution node identity mismatch")
    resolver = resolution.get("resolver")
    if (
        not isinstance(resolver, str)
        or not resolver.strip()
        or len(resolver) > MAX_RESOLVER_CHARS
    ):
        raise ValueError("checkpoint resolution resolver is invalid")
    _validate_timestamp(
        resolution.get("resolved_at"),
        field="checkpoint resolution timestamp",
    )


def activation_digest(record: dict[str, Any]) -> str:
    validate_activation_shape(record)
    return canonical_digest(record)


def validate_activation_shape(record: dict[str, Any]) -> None:
    if not isinstance(record, dict) or set(record) != _ACTIVATION_FIELDS:
        raise ValueError("workflow activation fields do not match schema")
    if (
        type(record.get("schema_version")) is not int
        or record["schema_version"] != ACTIVATION_SCHEMA_VERSION
    ):
        raise ValueError(
            f"workflow activation schema_version must be {ACTIVATION_SCHEMA_VERSION}"
        )
    _validate_canonical_id(record.get("workflow_id"), field="workflow activation workflow_id")
    if type(record.get("revision")) is not int or record["revision"] < 1:
        raise ValueError("workflow activation revision must be a positive integer")
    for field in (
        "revision_digest",
        "parent_tip_digest",
        "checkpoint_resolution_digest",
        "prior_state_digest",
    ):
        value = record.get(field)
        if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
            raise ValueError(f"workflow activation {field} must be a sha256 digest")
    _validate_canonical_id(
        record.get("checkpoint_node_id"),
        field="workflow activation checkpoint_node_id",
    )
    new_node_states = record.get("new_node_states")
    if not isinstance(new_node_states, dict) or not new_node_states:
        raise ValueError("workflow activation new_node_states must be a non-empty object")
    for node_id, node_state in new_node_states.items():
        _validate_canonical_id(node_id, field="workflow activation new node id")
        if node_state not in state.NODE_STATES:
            raise ValueError(f"unsupported workflow activation node state: {node_state!r}")
    _validate_timestamp(record.get("activated_at"), field="activation timestamp")
    if len(_canonical_bytes(record)) > MAX_ACTIVATION_FILE_BYTES:
        raise ValueError(f"workflow activation exceeds {MAX_ACTIVATION_FILE_BYTES} bytes")


def build_activation_record(
    base_manifest: dict[str, Any],
    prior_revisions: list[dict[str, Any]],
    next_revision: dict[str, Any],
    current_states: dict[str, str],
    checkpoint_resolution: dict[str, Any],
    *,
    activated_at: str | None = None,
) -> dict[str, Any]:
    revisions.validate_revision_sequence(base_manifest, [*prior_revisions, next_revision])
    workflow_id = str(base_manifest["id"])
    checkpoint_node_id = str(next_revision["checkpoint_node_id"])
    _validate_checkpoint_resolution(
        checkpoint_resolution,
        workflow_id=workflow_id,
        checkpoint_node_id=checkpoint_node_id,
    )
    projected = continuation.project_next_revision_states(
        base_manifest,
        prior_revisions,
        next_revision,
        current_states,
    )
    new_ids = [str(node["id"]) for node in next_revision["nodes"]]
    record = {
        "schema_version": ACTIVATION_SCHEMA_VERSION,
        "workflow_id": workflow_id,
        "revision": int(next_revision["revision"]),
        "revision_digest": revisions.revision_digest(next_revision),
        "parent_tip_digest": revisions.lineage_tip_digest(base_manifest, prior_revisions),
        "checkpoint_node_id": checkpoint_node_id,
        "checkpoint_resolution_digest": canonical_digest(checkpoint_resolution),
        "prior_state_digest": canonical_digest(current_states),
        "new_node_states": {node_id: projected[node_id] for node_id in new_ids},
        "activated_at": activated_at or _now_iso(),
    }
    validate_activation_shape(record)
    return record


class WorkflowRevisionActivationStore:
    """Create-only activation ledger kept separate from authoritative workflow state."""

    def __init__(
        self,
        workflow_store: WorkflowStore,
        revision_store: WorkflowRevisionStore | None = None,
    ) -> None:
        self.workflow_store = workflow_store
        self.revision_store = revision_store or WorkflowRevisionStore(workflow_store)

    def _root(self, workflow_id: str) -> Path:
        self.workflow_store.load_manifest(workflow_id)
        return self.workflow_store.root / workflow_id / "activations"

    def _path(self, workflow_id: str, revision: int) -> Path:
        if type(revision) is not int or revision < 1:
            raise ValueError("activation revision must be a positive integer")
        return self._root(workflow_id) / f"{revision:0{ACTIVATION_FILENAME_WIDTH}d}.json"

    def load(self, workflow_id: str) -> list[dict[str, Any]]:
        base = self.workflow_store.load_manifest(workflow_id)
        revision_chain = self.revision_store.load(workflow_id)
        root = self._root(workflow_id)
        if not root.exists():
            return []

        records: list[dict[str, Any]] = []
        for expected_revision, path in enumerate(sorted(root.glob("*.json")), start=1):
            expected_name = f"{expected_revision:0{ACTIVATION_FILENAME_WIDTH}d}.json"
            if path.name != expected_name:
                raise ValueError(
                    f"workflow activation files are not contiguous: expected {expected_name!r}, got {path.name!r}"
                )
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"workflow activation path must be a regular file: {path.name}")
            raw = path.read_bytes()
            if len(raw) > MAX_ACTIVATION_FILE_BYTES:
                raise ValueError(f"workflow activation exceeds bounds: {path.name}")
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid workflow activation file: {path.name}") from exc
            validate_activation_shape(payload)
            if payload["workflow_id"] != workflow_id:
                raise ValueError("workflow activation workflow identity mismatch")
            if payload["revision"] != expected_revision:
                raise ValueError("workflow activation revision number mismatch")
            if expected_revision > len(revision_chain):
                raise ValueError("workflow activation references a missing revision")
            revision = revision_chain[expected_revision - 1]
            if payload["revision_digest"] != revisions.revision_digest(revision):
                raise ValueError("workflow activation revision digest mismatch")
            prior = revision_chain[: expected_revision - 1]
            if payload["parent_tip_digest"] != revisions.lineage_tip_digest(base, prior):
                raise ValueError("workflow activation parent lineage mismatch")
            if payload["checkpoint_node_id"] != revision["checkpoint_node_id"]:
                raise ValueError("workflow activation checkpoint identity mismatch")
            expected_new_ids = {str(node["id"]) for node in revision["nodes"]}
            if set(payload["new_node_states"]) != expected_new_ids:
                raise ValueError("workflow activation new node states do not match revision")
            records.append(payload)
        return records

    def append(
        self,
        workflow_id: str,
        revision_number: int,
        current_states: dict[str, str],
        checkpoint_resolution: dict[str, Any],
        *,
        activated_at: str | None = None,
    ) -> dict[str, Any]:
        if type(revision_number) is not int or revision_number < 1:
            raise ValueError("activation revision must be a positive integer")
        with self.workflow_store.execution_lock(workflow_id):
            base = self.workflow_store.load_manifest(workflow_id)
            revision_chain = self.revision_store.load(workflow_id)
            if revision_number > len(revision_chain):
                raise ValueError(f"workflow revision {revision_number} does not exist")
            existing = self.load(workflow_id)
            if revision_number <= len(existing):
                current = existing[revision_number - 1]
                expected = build_activation_record(
                    base,
                    revision_chain[: revision_number - 1],
                    revision_chain[revision_number - 1],
                    current_states,
                    checkpoint_resolution,
                    activated_at=current["activated_at"],
                )
                if activation_digest(current) != activation_digest(expected):
                    raise ValueError(
                        f"workflow activation {revision_number} already exists with different provenance"
                    )
                return current
            expected_revision = len(existing) + 1
            if revision_number != expected_revision:
                raise ValueError(
                    f"workflow activation revision must be contiguous; expected {expected_revision}"
                )

            record = build_activation_record(
                base,
                revision_chain[: revision_number - 1],
                revision_chain[revision_number - 1],
                current_states,
                checkpoint_resolution,
                activated_at=activated_at,
            )
            target = self._path(workflow_id, revision_number)
            root = target.parent
            root.mkdir(parents=True, exist_ok=True)
            fsync_directory(root.parent)
            encoded = (
                json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
            ).encode("utf-8")
            try:
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                loaded = self.load(workflow_id)
                if revision_number > len(loaded):
                    raise ValueError(
                        "workflow activation appeared concurrently but ledger is incomplete"
                    )
                current = loaded[revision_number - 1]
                if activation_digest(current) != activation_digest(record):
                    raise ValueError(
                        f"workflow activation {revision_number} concurrently exists with different provenance"
                    )
                return current
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            fsync_directory(root)
            return self.load(workflow_id)[revision_number - 1]
