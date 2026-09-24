from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from local_agent.conversation import attention, records, state
from local_agent.conversation.store import WorkflowConversationStore
from local_agent.foundation.process import fsync_directory

CHECKPOINT_FILENAME_WIDTH = 6


def _json_text(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"


def _create_only(path: Path, payload: dict[str, Any], *, maximum: int) -> None:
    encoded = _json_text(payload).encode("utf-8")
    if len(encoded) > maximum:
        raise ValueError(f"conversation record exceeds {maximum} bytes")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    fsync_directory(path.parent)


class WorkflowConversationRecordLedger:
    """Checkpoint/terminal persistence owned by an existing conversation store.

    This object has no independent authority, graph, lock or top-level root. It always
    uses the bound WorkflowConversationStore request/state authority and the same
    WorkflowStore execution lock. Bridge attention emission is explicit and opt-in.
    """

    def __init__(
        self,
        conversation_store: WorkflowConversationStore,
        *,
        bridge_event_state_dir: Path | None = None,
    ) -> None:
        if not isinstance(conversation_store, WorkflowConversationStore):
            raise TypeError("conversation_store must be a WorkflowConversationStore")
        self.store = conversation_store
        self.bridge_event_state_dir = (
            Path(bridge_event_state_dir) if bridge_event_state_dir is not None else None
        )
        self.checkpoints_root = self.store.root / "checkpoints"
        self.terminals_root = self.store.root / "terminals"

    def _checkpoint_dir(self, request_id: str) -> Path:
        self.store._request_path(request_id)
        return self.checkpoints_root / request_id

    def _checkpoint_path(self, request_id: str, sequence: int) -> Path:
        if type(sequence) is not int or sequence < 1 or sequence > records.MAX_CHECKPOINTS:
            raise ValueError(
                f"child checkpoint sequence must be 1..{records.MAX_CHECKPOINTS}"
            )
        return self._checkpoint_dir(request_id) / (
            f"{sequence:0{CHECKPOINT_FILENAME_WIDTH}d}.json"
        )

    def _terminal_path(self, request_id: str) -> Path:
        self.store._request_path(request_id)
        return self.terminals_root / f"{request_id}.json"

    def _ensure_root(self, path: Path) -> None:
        self.store._ensure_layout()
        created = not path.exists()
        path.mkdir(exist_ok=True)
        if created:
            fsync_directory(self.store.root)

    def _ensure_checkpoint_dir(self, request_id: str) -> Path:
        self._ensure_root(self.checkpoints_root)
        path = self._checkpoint_dir(request_id)
        created = not path.exists()
        path.mkdir(exist_ok=True)
        if created:
            fsync_directory(self.checkpoints_root)
        return path

    def load_checkpoints(self, request_id: str) -> list[dict[str, Any]]:
        request = self.store.load_request(request_id)
        root = self._checkpoint_dir(request_id)
        if not root.exists():
            return []
        if root.is_symlink() or not root.is_dir():
            raise ValueError(f"child checkpoint directory is invalid: {request_id!r}")

        loaded: list[dict[str, Any]] = []
        for sequence, path in enumerate(sorted(root.glob("*.json")), start=1):
            expected_name = f"{sequence:0{CHECKPOINT_FILENAME_WIDTH}d}.json"
            if path.name != expected_name:
                raise ValueError(
                    "child checkpoint files are not contiguous: "
                    f"expected {expected_name!r}, got {path.name!r}"
                )
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"child checkpoint path must be a regular file: {path.name}")
            raw = path.read_bytes()
            if len(raw) > records.MAX_CHECKPOINT_BYTES + 1:
                raise ValueError(f"child checkpoint exceeds bounds: {path.name}")
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid child checkpoint file: {path.name}") from exc
            records.validate_child_checkpoint(payload, request=request)
            if payload["sequence"] != sequence:
                raise ValueError(
                    f"child checkpoint sequence mismatch in {path.name!r}: expected {sequence}"
                )
            loaded.append(payload)
        return loaded

    def append_checkpoint(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(checkpoint, dict):
            raise ValueError("child checkpoint must be an object")
        request_id = checkpoint.get("child_request_id")
        if not isinstance(request_id, str):
            raise ValueError("child checkpoint child_request_id must be a string")

        with self.store._mutation_lock():
            request = self.store.load_request(request_id)
            records.validate_child_checkpoint(checkpoint, request=request)
            lifecycle = self.store.load_state(request_id)
            if lifecycle["state"] != "active":
                raise ValueError("child checkpoints require active child state")

            existing = self.load_checkpoints(request_id)
            sequence = checkpoint["sequence"]
            if sequence <= len(existing):
                durable = existing[sequence - 1]
                if records.child_checkpoint_digest(
                    durable,
                    request=request,
                ) != records.child_checkpoint_digest(checkpoint, request=request):
                    raise ValueError(
                        f"child checkpoint {sequence} already exists with a different digest"
                    )
                return durable

            expected = len(existing) + 1
            if sequence != expected:
                raise ValueError(
                    f"child checkpoint sequence must be contiguous; expected {expected}"
                )

            self._ensure_checkpoint_dir(request_id)
            target = self._checkpoint_path(request_id, sequence)
            try:
                _create_only(target, checkpoint, maximum=records.MAX_CHECKPOINT_BYTES)
            except FileExistsError:
                reloaded = self.load_checkpoints(request_id)
                if sequence > len(reloaded):
                    raise ValueError(
                        f"child checkpoint {sequence} appeared concurrently but sequence is incomplete"
                    )
                durable = reloaded[sequence - 1]
                if records.child_checkpoint_digest(
                    durable,
                    request=request,
                ) != records.child_checkpoint_digest(checkpoint, request=request):
                    raise ValueError(
                        f"child checkpoint {sequence} concurrently exists with a different digest"
                    )
                return durable
            return self.load_checkpoints(request_id)[sequence - 1]

    def load_terminal(self, request_id: str) -> dict[str, Any] | None:
        path = self._terminal_path(request_id)
        if not path.exists():
            return None
        request = self.store.load_request(request_id)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"child terminal path must be a regular file: {request_id!r}")
        raw = path.read_bytes()
        if len(raw) > records.MAX_TERMINAL_BYTES + 1:
            raise ValueError(f"child terminal exceeds bounds: {request_id!r}")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid child terminal: {request_id!r}") from exc
        records.validate_child_terminal(payload, request=request)
        return payload

    def record_terminal(self, terminal: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(terminal, dict):
            raise ValueError("child terminal must be an object")
        request_id = terminal.get("child_request_id")
        if not isinstance(request_id, str):
            raise ValueError("child terminal child_request_id must be a string")

        with self.store._mutation_lock():
            request = self.store.load_request(request_id)
            records.validate_child_terminal(terminal, request=request)
            lifecycle = self.store.load_state(request_id)
            durable = self.load_terminal(request_id)

            if durable is None:
                if lifecycle["state"] == "active":
                    lifecycle = self._advance_child_state(
                        request_id,
                        lifecycle,
                        "terminal_pending_evidence",
                    )
                elif lifecycle["state"] != "terminal_pending_evidence":
                    raise ValueError(
                        "new child terminal requires active or terminal_pending_evidence state"
                    )
                self._ensure_root(self.terminals_root)
                try:
                    _create_only(
                        self._terminal_path(request_id),
                        terminal,
                        maximum=records.MAX_TERMINAL_BYTES,
                    )
                except FileExistsError:
                    pass
                durable = self.load_terminal(request_id)
                if durable is None:
                    raise ValueError("child terminal was not reconstructable after durable write")

            if records.child_terminal_digest(
                durable,
                request=request,
            ) != records.child_terminal_digest(terminal, request=request):
                raise ValueError("child terminal already exists with a different digest")

            lifecycle = self.store.load_state(request_id)
            if lifecycle["state"] == "terminal_pending_evidence":
                lifecycle = self._advance_child_state(
                    request_id,
                    lifecycle,
                    "terminal_recorded",
                )
            elif lifecycle["state"] not in {"terminal_recorded", "retired"}:
                raise ValueError(
                    "durable child terminal conflicts with child lifecycle state "
                    f"{lifecycle['state']!r}"
                )

            self._reconcile_workflow_outcome(request, durable)
            if self.bridge_event_state_dir is not None:
                attention.enqueue_child_terminal_attention(
                    request,
                    durable,
                    state_dir=self.bridge_event_state_dir,
                )
            return durable

    def _advance_child_state(
        self,
        request_id: str,
        lifecycle: dict[str, Any],
        target: str,
    ) -> dict[str, Any]:
        updated = dict(lifecycle)
        updated["state"] = state.transition_child_state(lifecycle["state"], target)
        from local_agent.conversation.store import now_iso

        updated["updated_at"] = now_iso()
        self.store._write_state(request_id, updated)
        return updated

    def _reconcile_workflow_outcome(
        self,
        request: dict[str, Any],
        terminal: dict[str, Any],
    ) -> None:
        node_id = request["workflow_node_id"]
        target = "succeeded" if terminal["outcome"] == "succeeded" else "failed"
        workflow = self.store.workflow_store.load_state(self.store.workflow_id)
        current = workflow["node_states"].get(node_id)
        if current is None:
            raise ValueError("terminal workflow node is absent from authoritative workflow state")
        if current == target:
            return
        if current != "waiting_conversation":
            raise ValueError(
                f"terminal outcome conflicts with workflow node state {current!r}"
            )
        self.store.workflow_store.set_node_state(self.store.workflow_id, node_id, target)
