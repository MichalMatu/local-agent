from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_agent.conversation import contract, state
from local_agent.foundation.process import atomic_write_text, fsync_directory
from local_agent.workflow import publishing, revisions
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore

CONVERSATION_STATE_SCHEMA_VERSION = 1
MAX_CONVERSATION_STATE_BYTES = 16 * 1024

_STATE_FIELDS = frozenset(
    {
        "schema_version",
        "child_request_id",
        "child_request_digest",
        "state",
        "created_at",
        "updated_at",
    }
)
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

_REGISTRATION_REQUIRED_STATES = frozenset(
    {
        "active",
        "terminal_pending_evidence",
        "terminal_recorded",
        "retired",
    }
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_text(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"


def _validate_request_id(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > contract.MAX_ID_CHARS
        or value != value.strip()
        or not _REQUEST_ID_RE.fullmatch(value)
    ):
        raise ValueError(
            "child request id must be a canonical non-empty identifier "
            f"up to {contract.MAX_ID_CHARS} characters"
        )
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


class WorkflowConversationStore:
    """Durable Conversation Fabric records owned by one existing workflow.

    The workflow DAG remains the graph authority. This store only persists the immutable
    request/registration records and the logical child lifecycle for reasoning nodes in
    that workflow. All mutations serialize through WorkflowStore.execution_lock().
    """

    def __init__(self, workflow_store: WorkflowStore, workflow_id: str) -> None:
        if not isinstance(workflow_store, WorkflowStore):
            raise TypeError("workflow_store must be a WorkflowStore")
        self.workflow_store = workflow_store
        base = self.workflow_store.load_manifest(workflow_id)
        self.workflow_id = str(base["id"])
        self.revision_store = WorkflowRevisionStore(self.workflow_store)
        self.root = self.workflow_store.root / self.workflow_id / "conversations"
        self.requests_root = self.root / "requests"
        self.registrations_root = self.root / "registrations"
        self.states_root = self.root / "state"

    def _request_path(self, request_id: str) -> Path:
        return self.requests_root / f"{_validate_request_id(request_id)}.json"

    def _registration_path(self, request_id: str) -> Path:
        return self.registrations_root / f"{_validate_request_id(request_id)}.json"

    def _state_path(self, request_id: str) -> Path:
        return self.states_root / f"{_validate_request_id(request_id)}.json"

    def _ensure_layout(self) -> None:
        self.workflow_store.load_manifest(self.workflow_id)
        workflow_dir = self.workflow_store.root / self.workflow_id
        root_created = not self.root.exists()
        self.root.mkdir(exist_ok=True)
        if root_created:
            fsync_directory(workflow_dir)

        for path in (self.requests_root, self.registrations_root, self.states_root):
            created = not path.exists()
            path.mkdir(exist_ok=True)
            if created:
                fsync_directory(self.root)

    def _mutation_lock(self):
        return self.workflow_store.execution_lock(self.workflow_id)

    def _validate_request_provenance(self, request: dict[str, Any]) -> None:
        contract.validate_child_request(request)
        if request["workflow_id"] != self.workflow_id:
            raise ValueError(
                "child request workflow mismatch: "
                f"expected {self.workflow_id!r}, got {request['workflow_id']!r}"
            )

        base = self.workflow_store.load_manifest(self.workflow_id)
        chain = self.revision_store.load(self.workflow_id)
        revision, introduction_digest = publishing.node_introduction_identity(
            base,
            chain,
            str(request["workflow_node_id"]),
        )
        contract.require_child_request_workflow_provenance(
            request,
            workflow_id=self.workflow_id,
            workflow_node_id=str(request["workflow_node_id"]),
            workflow_node_revision=revision,
            workflow_node_introduction_digest=introduction_digest,
        )

        effective = revisions.effective_manifest(base, chain)
        node = next(
            (
                item
                for item in effective["nodes"]
                if item["id"] == request["workflow_node_id"]
            ),
            None,
        )
        if not isinstance(node, dict):
            raise ValueError("child request workflow node is unavailable")
        if node["kind"] != "reasoning":
            raise ValueError("child request workflow node must be a reasoning node")
        contract.require_child_request_target(
            request,
            repository_id=str(node["repository_id"]),
            agent_binding=str(node["agent_binding"]),
        )

    def _require_new_request_ready(self, request: dict[str, Any]) -> None:
        workflow_state = self.workflow_store.load_state(self.workflow_id)
        node_id = str(request["workflow_node_id"])
        node_state = workflow_state["node_states"].get(node_id)
        if node_state is None:
            raise ValueError(
                "child request workflow node is not represented by the active workflow state"
            )
        if node_state != "waiting_conversation":
            raise ValueError(
                f"child request workflow node must be waiting_conversation before admission; "
                f"got {node_state!r}"
            )

    def request_ids(self) -> list[str]:
        if not self.requests_root.exists():
            return []
        request_ids: list[str] = []
        for path in self.requests_root.glob("*.json"):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                request_id = _validate_request_id(path.name[:-5])
            except ValueError:
                continue
            request_ids.append(request_id)
        return sorted(request_ids)

    def request_for_node(self, node_id: str) -> dict[str, Any] | None:
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("workflow node id must be a non-empty string")
        match: dict[str, Any] | None = None
        for request_id in self.request_ids():
            request = self.load_request(request_id)
            if request["workflow_node_id"] != node_id:
                continue
            if match is not None and match["id"] != request["id"]:
                raise ValueError(
                    f"workflow reasoning node {node_id!r} has multiple durable child requests: "
                    f"{match['id']!r} and {request['id']!r}"
                )
            match = request
        return match

    def admit_request(self, request: dict[str, Any]) -> dict[str, Any]:
        contract.validate_child_request(request)
        request_id = _validate_request_id(request["id"])
        digest = contract.child_request_digest(request)
        with self._mutation_lock():
            self._validate_request_provenance(request)
            self._ensure_layout()
            path = self._request_path(request_id)
            if path.exists():
                existing = self.load_request(request_id)
                if contract.child_request_digest(existing) != digest:
                    raise ValueError(
                        f"child request {request_id!r} already exists with a different digest"
                    )
                if not self._state_path(request_id).exists():
                    self._write_state(request_id, self._initial_state(existing))
                return self.load_state(request_id)

            node_id = str(request["workflow_node_id"])
            existing_for_node = self.request_for_node(node_id)
            if existing_for_node is not None:
                raise ValueError(
                    f"workflow reasoning node {node_id!r} already has child request "
                    f"{existing_for_node['id']!r}"
                )

            self._require_new_request_ready(request)
            atomic_write_text(path, _json_text(request))
            self._write_state(request_id, self._initial_state(request))
            return self.load_state(request_id)

    def load_request(self, request_id: str) -> dict[str, Any]:
        canonical = _validate_request_id(request_id)
        path = self._request_path(canonical)
        try:
            if path.is_symlink() or not path.is_file():
                raise OSError("request path is not a regular file")
            raw = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"child request is unavailable: {canonical!r}") from exc
        if len(raw) > contract.MAX_CHILD_REQUEST_BYTES + 1:
            raise ValueError(f"invalid child request: {canonical!r}: file exceeds bounds")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid child request: {canonical!r}") from exc
        try:
            self._validate_request_provenance(payload)
        except ValueError as exc:
            raise ValueError(f"invalid child request: {canonical!r}: {exc}") from exc
        if payload["id"] != canonical:
            raise ValueError(
                f"child request identity mismatch: expected {canonical!r}, got {payload['id']!r}"
            )
        return payload

    def load_registration(self, request_id: str) -> dict[str, Any] | None:
        canonical = _validate_request_id(request_id)
        path = self._registration_path(canonical)
        if not path.exists():
            return None
        request = self.load_request(canonical)
        try:
            if path.is_symlink() or not path.is_file():
                raise OSError("registration path is not a regular file")
            raw = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"child registration is unavailable: {canonical!r}") from exc
        if len(raw) > contract.MAX_CHILD_REGISTRATION_BYTES + 1:
            raise ValueError(
                f"invalid child registration: {canonical!r}: file exceeds bounds"
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid child registration: {canonical!r}") from exc
        try:
            contract.validate_child_registration(payload, request=request)
        except ValueError as exc:
            raise ValueError(f"invalid child registration: {canonical!r}: {exc}") from exc
        if payload["child_request_id"] != canonical:
            raise ValueError(
                "child registration identity mismatch: "
                f"expected {canonical!r}, got {payload['child_request_id']!r}"
            )
        return payload

    def load_state(self, request_id: str) -> dict[str, Any]:
        canonical = _validate_request_id(request_id)
        request = self.load_request(canonical)
        path = self._state_path(canonical)
        try:
            if path.is_symlink() or not path.is_file():
                raise OSError("state path is not a regular file")
            raw = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"conversation state is unavailable: {canonical!r}") from exc
        if len(raw) > MAX_CONVERSATION_STATE_BYTES:
            raise ValueError(
                f"invalid conversation state: {canonical!r}: file exceeds bounds"
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid conversation state: {canonical!r}") from exc
        try:
            self._validate_state_payload(request, payload)
        except ValueError as exc:
            raise ValueError(f"invalid conversation state: {canonical!r}: {exc}") from exc
        return payload

    def transition_state(self, request_id: str, target: str) -> dict[str, Any]:
        canonical = _validate_request_id(request_id)
        with self._mutation_lock():
            current = self.load_state(canonical)
            next_state = state.transition_child_state(current["state"], target)
            if next_state == current["state"]:
                return current
            if next_state == "active" and self.load_registration(canonical) is None:
                raise ValueError("active child state requires a durable registration")
            updated = dict(current)
            updated["state"] = next_state
            updated["updated_at"] = now_iso()
            self._write_state(canonical, updated)
            return updated

    def register_child(self, registration: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(registration, dict):
            raise ValueError("child registration must be an object")
        request_id = _validate_request_id(registration.get("child_request_id"))
        with self._mutation_lock():
            request = self.load_request(request_id)
            contract.validate_child_registration(registration, request=request)
            current = self.load_state(request_id)
            existing = self.load_registration(request_id)
            if existing is None:
                if current["state"] != "registration_pending":
                    raise ValueError(
                        "new child registration requires registration_pending state"
                    )
                atomic_write_text(
                    self._registration_path(request_id),
                    _json_text(registration),
                )
                resolved = dict(registration)
            else:
                resolved = contract.reconcile_child_registration(
                    existing,
                    registration,
                    request=request,
                )

            if current["state"] == "registration_pending":
                updated = dict(current)
                updated["state"] = state.transition_child_state(
                    current["state"],
                    "active",
                )
                updated["updated_at"] = now_iso()
                self._write_state(request_id, updated)
            return resolved

    def _initial_state(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": CONVERSATION_STATE_SCHEMA_VERSION,
            "child_request_id": request["id"],
            "child_request_digest": contract.child_request_digest(request),
            "state": state.initial_child_state(),
            "created_at": request["created_at"],
            "updated_at": request["created_at"],
        }

    def _validate_state_payload(
        self,
        request: dict[str, Any],
        payload: Any,
    ) -> None:
        if not isinstance(payload, dict) or set(payload) != _STATE_FIELDS:
            raise ValueError("state fields do not match schema")
        if (
            type(payload.get("schema_version")) is not int
            or payload["schema_version"] != CONVERSATION_STATE_SCHEMA_VERSION
        ):
            raise ValueError(
                f"state schema_version must be {CONVERSATION_STATE_SCHEMA_VERSION}"
            )
        request_id = _validate_request_id(payload.get("child_request_id"))
        if request_id != request["id"]:
            raise ValueError("state child_request_id does not match request")
        digest = contract.child_request_digest(request)
        if payload.get("child_request_digest") != digest:
            raise ValueError("state child_request_digest does not match request")
        child_state = state.validate_child_state(payload.get("state"))
        if payload.get("created_at") != request["created_at"]:
            raise ValueError("state created_at does not match request")
        _validate_timestamp(payload.get("created_at"), field="state created_at")
        _validate_timestamp(payload.get("updated_at"), field="state updated_at")

        registration = self.load_registration(request_id)
        if child_state == "requested" and registration is not None:
            raise ValueError("requested child state cannot already have a registration")
        if child_state in _REGISTRATION_REQUIRED_STATES and registration is None:
            raise ValueError(f"{child_state} child state requires a durable registration")

    def _write_state(self, request_id: str, payload: dict[str, Any]) -> None:
        request = self.load_request(request_id)
        self._validate_state_payload(request, payload)
        text = _json_text(payload)
        if len(text.encode("utf-8")) > MAX_CONVERSATION_STATE_BYTES:
            raise ValueError(
                f"conversation state exceeds {MAX_CONVERSATION_STATE_BYTES} bytes"
            )
        atomic_write_text(self._state_path(request_id), text)
