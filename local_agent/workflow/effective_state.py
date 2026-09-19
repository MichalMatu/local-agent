from __future__ import annotations

import contextlib
import fcntl
import json
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_agent.foundation.process import atomic_write_text
from local_agent.workflow import activation, contract, revisions, state
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore

EFFECTIVE_STATE_SCHEMA_VERSION = 1
MAX_EFFECTIVE_STATE_BYTES = 1024 * 1024
MAX_RESOLVER_CHARS = 200
MAX_NOTE_CHARS = 4096
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

_FIELDS = {
    "schema_version",
    "workflow_id",
    "base_manifest_digest",
    "base_state_digest",
    "active_revision",
    "lineage_tip_digest",
    "activation_digest",
    "workflow_state",
    "node_states",
    "gate_decisions",
    "planner_checkpoints",
    "created_at",
    "updated_at",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


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


class WorkflowEffectiveStateStore:
    """Isolated state ledger for activated revision graphs.

    This file is deliberately separate from WorkflowStore.state.json and is not consumed
    by the production coordinator. It exists to prove multi-revision state semantics
    before any migration or runtime wiring is attempted.
    """

    def __init__(
        self,
        workflow_store: WorkflowStore,
        revision_store: WorkflowRevisionStore | None = None,
        activation_store: WorkflowRevisionActivationStore | None = None,
    ) -> None:
        self.workflow_store = workflow_store
        self.revision_store = revision_store or WorkflowRevisionStore(workflow_store)
        self.activation_store = activation_store or WorkflowRevisionActivationStore(
            workflow_store,
            self.revision_store,
        )
        self.lock_root = workflow_store.state_dir / "locks" / "workflow-effective-state"

    def _path(self, workflow_id: str) -> Path:
        contract.validate_workflow_id(workflow_id)
        self.workflow_store.load_manifest(workflow_id)
        return self.workflow_store.root / workflow_id / "effective_state.json"

    @contextlib.contextmanager
    def _lock(self, workflow_id: str) -> Iterator[None]:
        canonical = contract.validate_workflow_id(workflow_id)
        self.lock_root.mkdir(parents=True, exist_ok=True)
        path = self.lock_root / f"{canonical}.lock"
        with path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def initialize(self, workflow_id: str) -> dict[str, Any]:
        """Create effective state from base state plus exactly the first activation."""
        with self._lock(workflow_id):
            path = self._path(workflow_id)
            if path.exists():
                return self.load(workflow_id)

            base = self.workflow_store.load_manifest(workflow_id)
            base_state = self.workflow_store.load_state(workflow_id)
            revision_chain = self.revision_store.load(workflow_id)
            activations = self.activation_store.load(workflow_id)
            if not revision_chain or not activations:
                raise ValueError("effective state requires at least one activated revision")
            first = activations[0]
            if first["revision"] != 1:
                raise ValueError("effective state requires activation revision 1")

            base_node_states = dict(base_state["node_states"])
            if first["prior_state_digest"] != activation.canonical_digest(base_node_states):
                raise ValueError("first activation prior state does not match base workflow state")
            checkpoint_resolution = base_state["planner_checkpoints"].get(
                first["checkpoint_node_id"]
            )
            if not isinstance(checkpoint_resolution, dict):
                raise ValueError("first activation checkpoint resolution is missing from base state")
            if first["checkpoint_resolution_digest"] != activation.canonical_digest(
                checkpoint_resolution
            ):
                raise ValueError("first activation checkpoint resolution digest mismatch")

            node_states = dict(base_node_states)
            node_states.update(first["new_node_states"])
            effective_manifest = revisions.effective_manifest(base, revision_chain[:1])
            normalized = state.advance_dependency_states(effective_manifest, node_states)
            if normalized != node_states:
                raise ValueError("first activation new node states are not dependency-normalized")

            timestamp = _now_iso()
            payload = {
                "schema_version": EFFECTIVE_STATE_SCHEMA_VERSION,
                "workflow_id": workflow_id,
                "base_manifest_digest": contract.manifest_digest(base),
                "base_state_digest": activation.canonical_digest(base_node_states),
                "active_revision": 1,
                "lineage_tip_digest": revisions.lineage_tip_digest(
                    base,
                    revision_chain[:1],
                ),
                "activation_digest": activation.activation_digest(first),
                "workflow_state": state.workflow_state(node_states),
                "node_states": node_states,
                "gate_decisions": dict(base_state["gate_decisions"]),
                "planner_checkpoints": dict(base_state["planner_checkpoints"]),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            self._write(workflow_id, payload)
            return payload

    def load(self, workflow_id: str) -> dict[str, Any]:
        path = self._path(workflow_id)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"effective workflow state is unavailable: {workflow_id!r}") from exc
        if len(raw) > MAX_EFFECTIVE_STATE_BYTES:
            raise ValueError("effective workflow state exceeds bounds")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid effective workflow state") from exc
        self._validate(workflow_id, payload)
        return payload

    def set_task_node_state(
        self,
        workflow_id: str,
        node_id: str,
        target: str,
    ) -> dict[str, Any]:
        """Advance a task node in the isolated effective graph only."""
        with self._lock(workflow_id):
            current = self.load(workflow_id)
            manifest = self._active_manifest(workflow_id, current)
            node = self._node(manifest, node_id)
            if node["kind"] != "task":
                raise ValueError(f"effective workflow node {node_id!r} is not a task")
            node_states = dict(current["node_states"])
            node_states[node_id] = state.transition_node_state(node_states[node_id], target)
            node_states = state.advance_dependency_states(manifest, node_states)
            if node_states == current["node_states"]:
                return current
            updated = dict(current)
            updated["node_states"] = node_states
            updated["workflow_state"] = state.workflow_state(node_states)
            updated["updated_at"] = _now_iso()
            self._write(workflow_id, updated)
            return updated

    def resolve_planner_checkpoint(
        self,
        workflow_id: str,
        node_id: str,
        *,
        resolver: str,
        note: str | None = None,
        resolved_at: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a checkpoint in the isolated effective graph with durable provenance."""
        if (
            not isinstance(resolver, str)
            or not resolver.strip()
            or len(resolver) > MAX_RESOLVER_CHARS
        ):
            raise ValueError("effective checkpoint resolver must be a non-empty bounded string")
        if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE_CHARS):
            raise ValueError("effective checkpoint note must be null or bounded text")
        timestamp = resolved_at or _now_iso()
        _validate_timestamp(timestamp, field="effective checkpoint resolution timestamp")

        with self._lock(workflow_id):
            current = self.load(workflow_id)
            manifest = self._active_manifest(workflow_id, current)
            node = self._node(manifest, node_id)
            if node["kind"] != "planner_checkpoint":
                raise ValueError(f"effective workflow node {node_id!r} is not a planner checkpoint")
            existing = current["planner_checkpoints"].get(node_id)
            if isinstance(existing, dict):
                return dict(existing)
            if current["node_states"][node_id] != "waiting_planner":
                raise ValueError(f"effective planner checkpoint {node_id!r} is not waiting")

            record = {
                "schema_version": 1,
                "workflow_id": workflow_id,
                "lineage_tip_digest": current["lineage_tip_digest"],
                "node_id": node_id,
                "resolver": resolver,
                "note": note,
                "resolved_at": timestamp,
            }
            node_states = dict(current["node_states"])
            node_states[node_id] = state.transition_node_state(
                node_states[node_id],
                "succeeded",
            )
            node_states = state.advance_dependency_states(manifest, node_states)
            checkpoints = dict(current["planner_checkpoints"])
            checkpoints[node_id] = record
            updated = dict(current)
            updated["node_states"] = node_states
            updated["planner_checkpoints"] = checkpoints
            updated["workflow_state"] = state.workflow_state(node_states)
            updated["updated_at"] = _now_iso()
            self._write(workflow_id, updated)
            return record

    def activate_next_revision(self, workflow_id: str) -> dict[str, Any]:
        """Apply the next pre-created activation record to isolated effective state."""
        with self._lock(workflow_id):
            current = self.load(workflow_id)
            next_revision = int(current["active_revision"]) + 1
            revision_chain = self.revision_store.load(workflow_id)
            activations = self.activation_store.load(workflow_id)
            if next_revision > len(revision_chain):
                raise ValueError("no next workflow revision exists")
            if next_revision > len(activations):
                raise ValueError("next workflow revision has not been activated")
            record = activations[next_revision - 1]
            if record["prior_state_digest"] != activation.canonical_digest(
                current["node_states"]
            ):
                raise ValueError("next activation prior state does not match effective state")
            checkpoint_resolution = current["planner_checkpoints"].get(
                record["checkpoint_node_id"]
            )
            if not isinstance(checkpoint_resolution, dict):
                raise ValueError("next activation checkpoint resolution is missing")
            if record["checkpoint_resolution_digest"] != activation.canonical_digest(
                checkpoint_resolution
            ):
                raise ValueError("next activation checkpoint resolution digest mismatch")
            if record["parent_tip_digest"] != current["lineage_tip_digest"]:
                raise ValueError("next activation parent lineage does not match effective state")

            before_states = dict(current["node_states"])
            node_states = dict(before_states)
            node_states.update(record["new_node_states"])
            base = self.workflow_store.load_manifest(workflow_id)
            manifest = revisions.effective_manifest(
                base,
                revision_chain[:next_revision],
            )
            normalized = state.advance_dependency_states(manifest, node_states)
            if normalized != node_states:
                raise ValueError("next activation new node states are not dependency-normalized")
            for node_id, old_state in before_states.items():
                if node_states[node_id] != old_state:
                    raise ValueError("next activation changed an existing effective node state")

            updated = dict(current)
            updated["active_revision"] = next_revision
            updated["lineage_tip_digest"] = revisions.lineage_tip_digest(
                base,
                revision_chain[:next_revision],
            )
            updated["activation_digest"] = activation.activation_digest(record)
            updated["node_states"] = node_states
            updated["workflow_state"] = state.workflow_state(node_states)
            updated["updated_at"] = _now_iso()
            self._write(workflow_id, updated)
            return updated

    def _active_manifest(
        self,
        workflow_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        base = self.workflow_store.load_manifest(workflow_id)
        revision_chain = self.revision_store.load(workflow_id)
        active_revision = int(payload["active_revision"])
        return revisions.effective_manifest(base, revision_chain[:active_revision])

    @staticmethod
    def _node(manifest: dict[str, Any], node_id: str) -> dict[str, Any]:
        for node in manifest["nodes"]:
            if node["id"] == node_id:
                return node
        raise ValueError(f"unknown effective workflow node: {node_id!r}")

    def _validate(self, workflow_id: str, payload: Any) -> None:
        if not isinstance(payload, dict) or set(payload) != _FIELDS:
            raise ValueError("effective workflow state fields do not match schema")
        if (
            type(payload.get("schema_version")) is not int
            or payload["schema_version"] != EFFECTIVE_STATE_SCHEMA_VERSION
        ):
            raise ValueError(
                f"effective workflow state schema_version must be {EFFECTIVE_STATE_SCHEMA_VERSION}"
            )
        if payload.get("workflow_id") != workflow_id:
            raise ValueError("effective workflow state identity mismatch")
        for field in (
            "base_manifest_digest",
            "base_state_digest",
            "lineage_tip_digest",
            "activation_digest",
        ):
            value = payload.get(field)
            if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
                raise ValueError(f"effective workflow state {field} must be a sha256 digest")
        if type(payload.get("active_revision")) is not int or payload["active_revision"] < 1:
            raise ValueError("effective workflow state active_revision must be positive")
        if not isinstance(payload.get("gate_decisions"), dict):
            raise ValueError("effective workflow gate_decisions must be an object")
        if not isinstance(payload.get("planner_checkpoints"), dict):
            raise ValueError("effective workflow planner_checkpoints must be an object")
        _validate_timestamp(payload.get("created_at"), field="effective state created_at")
        _validate_timestamp(payload.get("updated_at"), field="effective state updated_at")

        base = self.workflow_store.load_manifest(workflow_id)
        if payload["base_manifest_digest"] != contract.manifest_digest(base):
            raise ValueError("effective workflow base manifest digest mismatch")
        revision_chain = self.revision_store.load(workflow_id)
        activations = self.activation_store.load(workflow_id)
        active_revision = int(payload["active_revision"])
        if active_revision > len(revision_chain) or active_revision > len(activations):
            raise ValueError("effective workflow state references unavailable revision activation")
        if payload["lineage_tip_digest"] != revisions.lineage_tip_digest(
            base,
            revision_chain[:active_revision],
        ):
            raise ValueError("effective workflow lineage tip mismatch")
        if payload["activation_digest"] != activation.activation_digest(
            activations[active_revision - 1]
        ):
            raise ValueError("effective workflow activation digest mismatch")

        manifest = revisions.effective_manifest(base, revision_chain[:active_revision])
        node_states = payload.get("node_states")
        if not isinstance(node_states, dict):
            raise ValueError("effective workflow node_states must be an object")
        expected_ids = {str(node["id"]) for node in manifest["nodes"]}
        if set(node_states) != expected_ids:
            raise ValueError("effective workflow node states do not match active graph")
        normalized = state.advance_dependency_states(manifest, node_states)
        if normalized != node_states:
            raise ValueError("effective workflow node states are not dependency-normalized")
        expected_workflow_state = state.workflow_state(node_states)
        if payload.get("workflow_state") != expected_workflow_state:
            raise ValueError("effective workflow state classification mismatch")

    def _write(self, workflow_id: str, payload: dict[str, Any]) -> None:
        self._validate(workflow_id, payload)
        text = _json_text(payload)
        if len(text.encode("utf-8")) > MAX_EFFECTIVE_STATE_BYTES:
            raise ValueError("effective workflow state exceeds bounds")
        atomic_write_text(self._path(workflow_id), text)
