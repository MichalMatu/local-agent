from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from local_agent.foundation import storage
from local_agent.repository.context import RepositoryContext
from local_agent.workflow import evidence
from local_agent.workflow.git_control_plane import (
    GitWorkflowControlPlane,
    WorkflowGitIntegrityError,
    WorkflowGitPublicationAmbiguous,
    WorkflowGitPublicationConflict,
    WorkflowGitRepositoryBusyError,
    _canonical_json_text,
    _canonical_task_id,
    _require_success,
)

_CONTROL_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
_CANCEL_REQUEST_PATH = ".agent/daemon/control.json"
_CANCEL_ACK_DIR = ".agent/daemon/acks"


class CancelRequestState(Enum):
    NOT_NEEDED = "not_needed"
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CancelRequestEvidence:
    state: CancelRequestState
    control_id: str
    task_id: str
    ack: dict[str, Any] | None = None


def cancel_control_id(
    repository_id: str,
    task_id: str,
    expected_task_digest: str,
) -> str:
    task_id = _canonical_task_id(task_id)
    if not isinstance(repository_id, str) or not repository_id:
        raise ValueError("repository_id must be non-empty")
    if (
        not isinstance(expected_task_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_task_digest)
    ):
        raise ValueError("expected_task_digest must be 64 lowercase hex characters")
    encoded = json.dumps(
        [repository_id, task_id, expected_task_digest],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "wf-cancel-" + hashlib.sha256(encoded).hexdigest()


def _validate_ack(
    payload: dict[str, Any],
    *,
    control_id: str,
    task_id: str,
) -> CancelRequestEvidence:
    if payload.get("id") != control_id:
        raise WorkflowGitIntegrityError("workflow cancel ACK control id mismatch")
    if payload.get("action") != "cancel_task":
        raise WorkflowGitIntegrityError("workflow cancel ACK action mismatch")
    if payload.get("task_id") != task_id:
        raise WorkflowGitIntegrityError("workflow cancel ACK task id mismatch")
    status = payload.get("status")
    if status == "accepted":
        state = CancelRequestState.ACCEPTED
    elif status == "completed":
        state = CancelRequestState.COMPLETED
    elif status == "rejected":
        state = CancelRequestState.REJECTED
    else:
        raise WorkflowGitIntegrityError(
            f"workflow cancel ACK has unsupported status: {status!r}"
        )
    return CancelRequestEvidence(
        state=state,
        control_id=control_id,
        task_id=task_id,
        ack=dict(payload),
    )


class GitWorkflowCancellationTransport:
    """Unwired publisher for the existing repository `cancel_task` protocol.

    ACK evidence only proves the control request was handled. Workflow task state must
    still reconcile from the exact task result/status evidence through the normal
    coordinator path; an `accepted` or `completed` ACK never directly marks a node
    cancelled.
    """

    def __init__(self, control_plane: GitWorkflowControlPlane) -> None:
        self.control_plane = control_plane

    @staticmethod
    def _request_payload(control_id: str, task_id: str) -> dict[str, str]:
        if not _CONTROL_ID_RE.fullmatch(control_id):
            raise ValueError("cancel control id is invalid")
        return {
            "id": control_id,
            "action": "cancel_task",
            "task_id": task_id,
        }

    def _ack_locked(
        self,
        repository: RepositoryContext,
        control_id: str,
        task_id: str,
    ) -> CancelRequestEvidence | None:
        payload = self.control_plane._read_json_path(
            repository,
            f"{_CANCEL_ACK_DIR}/{control_id}.json",
        )
        if payload is None:
            return None
        return _validate_ack(payload, control_id=control_id, task_id=task_id)

    def _existing_request_locked(
        self,
        repository: RepositoryContext,
    ) -> dict[str, Any] | None:
        payload = self.control_plane._read_json_path(repository, _CANCEL_REQUEST_PATH)
        if payload is None:
            return None
        control_id = payload.get("id")
        if not isinstance(control_id, str) or not _CONTROL_ID_RE.fullmatch(control_id):
            raise WorkflowGitIntegrityError("existing repository control request has invalid id")
        return payload

    def _existing_request_is_acknowledged_locked(
        self,
        repository: RepositoryContext,
        request: dict[str, Any],
    ) -> bool:
        control_id = str(request["id"])
        ack = self.control_plane._read_json_path(
            repository,
            f"{_CANCEL_ACK_DIR}/{control_id}.json",
        )
        if ack is None:
            return False
        if ack.get("id") != control_id or ack.get("action") != request.get("action"):
            raise WorkflowGitIntegrityError("existing repository control ACK identity mismatch")
        if ack.get("status") not in {"accepted", "completed", "rejected"}:
            raise WorkflowGitIntegrityError("existing repository control ACK status is invalid")
        return True

    def inspect(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_task_digest: str,
    ) -> CancelRequestEvidence:
        task_id = _canonical_task_id(task_id)
        control_id = cancel_control_id(
            repository.repository_id,
            task_id,
            expected_task_digest,
        )
        with self.control_plane._repository_lock(repository):
            self.control_plane._sync_locked(repository)
            ack = self._ack_locked(repository, control_id, task_id)
            if ack is not None:
                return ack
            child = self.control_plane._inspect_locked(
                repository,
                task_id,
                expected_task_digest,
            )
            if child.kind in {
                evidence.ChildEvidenceKind.SUCCEEDED,
                evidence.ChildEvidenceKind.FAILED,
                evidence.ChildEvidenceKind.CANCELLED,
                evidence.ChildEvidenceKind.INTERRUPTED,
            }:
                return CancelRequestEvidence(
                    state=CancelRequestState.NOT_NEEDED,
                    control_id=control_id,
                    task_id=task_id,
                )
            request = self._existing_request_locked(repository)
            if request == self._request_payload(control_id, task_id):
                return CancelRequestEvidence(
                    state=CancelRequestState.REQUESTED,
                    control_id=control_id,
                    task_id=task_id,
                )
            return CancelRequestEvidence(
                state=CancelRequestState.NOT_NEEDED,
                control_id=control_id,
                task_id=task_id,
            )

    def _remote_request_payload(
        self,
        repository: RepositoryContext,
    ) -> dict[str, Any] | None:
        remote_ref = f"refs/remotes/origin/{repository.control_branch}"
        result = self.control_plane._git(
            repository,
            ["show", f"{remote_ref}:{_CANCEL_REQUEST_PATH}"],
            timeout=30,
        )
        if result["exit_code"] != 0:
            return None
        text = str(result.get("output", ""))
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise WorkflowGitIntegrityError("remote workflow cancel request is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise WorkflowGitIntegrityError("remote workflow cancel request must be an object")
        return payload

    def _recover_failed_push(
        self,
        repository: RepositoryContext,
        request: dict[str, str],
        *,
        base_head: str,
        push_result: dict[str, Any],
    ) -> None:
        self.control_plane._reset_to(repository, base_head)
        fetch = self.control_plane._fetch_remote(repository)
        if fetch["exit_code"] != 0:
            raise WorkflowGitPublicationAmbiguous(
                "workflow cancel push failed and remote request could not be proven: "
                + storage.git_failure_diagnostic(push_result)
            )
        remote_ref = f"refs/remotes/origin/{repository.control_branch}"
        remote_request = self._remote_request_payload(repository)
        _require_success(
            self.control_plane._git(
                repository,
                ["reset", "--hard", remote_ref],
                timeout=60,
            ),
            "align workflow cancel checkout after failed push",
        )
        self.control_plane._require_clean(repository)
        if remote_request == request:
            return
        raise WorkflowGitPublicationConflict(
            "workflow cancel request was not proven after concurrent remote update"
        )

    def request_cancel(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_task_digest: str,
    ) -> CancelRequestEvidence:
        task_id = _canonical_task_id(task_id)
        control_id = cancel_control_id(
            repository.repository_id,
            task_id,
            expected_task_digest,
        )
        request = self._request_payload(control_id, task_id)

        with self.control_plane._repository_lock(repository):
            self.control_plane._sync_locked(repository)
            ack = self._ack_locked(repository, control_id, task_id)
            if ack is not None:
                return ack

            child = self.control_plane._inspect_locked(
                repository,
                task_id,
                expected_task_digest,
            )
            if child.kind == evidence.ChildEvidenceKind.DIGEST_MISMATCH:
                raise WorkflowGitIntegrityError(
                    f"refusing workflow cancel for mismatched task evidence: {task_id}"
                )
            if child.kind == evidence.ChildEvidenceKind.ABSENT:
                raise WorkflowGitIntegrityError(
                    f"refusing workflow cancel for missing task evidence: {task_id}"
                )
            if child.kind in {
                evidence.ChildEvidenceKind.SUCCEEDED,
                evidence.ChildEvidenceKind.FAILED,
                evidence.ChildEvidenceKind.CANCELLED,
                evidence.ChildEvidenceKind.INTERRUPTED,
            }:
                return CancelRequestEvidence(
                    state=CancelRequestState.NOT_NEEDED,
                    control_id=control_id,
                    task_id=task_id,
                )

            existing = self._existing_request_locked(repository)
            if existing == request:
                return CancelRequestEvidence(
                    state=CancelRequestState.REQUESTED,
                    control_id=control_id,
                    task_id=task_id,
                )
            if existing is not None and not self._existing_request_is_acknowledged_locked(
                repository,
                existing,
            ):
                raise WorkflowGitRepositoryBusyError(
                    "repository already has an unacknowledged control request"
                )

            head = _require_success(
                self.control_plane._git(repository, ["rev-parse", "HEAD"], timeout=30),
                "read workflow cancel base HEAD",
            )
            base_head = str(head.get("output", "")).strip()
            target = self.control_plane._safe_path(repository, _CANCEL_REQUEST_PATH)
            target.parent.mkdir(parents=True, exist_ok=True)
            encoded = _canonical_json_text(request).encode("utf-8")
            temp = target.with_name(target.name + f".tmp-{os.getpid()}")
            try:
                with temp.open("xb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, target)
                _require_success(
                    self.control_plane._git(
                        repository,
                        ["add", "--", _CANCEL_REQUEST_PATH],
                        timeout=30,
                    ),
                    "stage workflow cancel request",
                )
                staged = _require_success(
                    self.control_plane._git(
                        repository,
                        ["diff", "--cached", "--name-only"],
                        timeout=30,
                    ),
                    "inspect staged workflow cancel request",
                )
                staged_paths = tuple(
                    line.strip()
                    for line in str(staged.get("output", "")).splitlines()
                    if line.strip()
                )
                if staged_paths != (_CANCEL_REQUEST_PATH,):
                    raise WorkflowGitIntegrityError(
                        f"workflow cancel staged unexpected paths: {staged_paths!r}"
                    )
                _require_success(
                    self.control_plane._git(
                        repository,
                        [
                            "commit",
                            "-m",
                            f"Request workflow task cancellation {control_id}",
                            "--",
                            _CANCEL_REQUEST_PATH,
                        ],
                        timeout=60,
                    ),
                    "commit workflow cancel request",
                )
            except Exception:
                temp.unlink(missing_ok=True)
                self.control_plane._reset_to(repository, base_head)
                raise
            finally:
                temp.unlink(missing_ok=True)

            push = self.control_plane._push_control_branch(repository)
            if push["exit_code"] != 0:
                self._recover_failed_push(
                    repository,
                    request,
                    base_head=base_head,
                    push_result=push,
                )

            self.control_plane._require_clean(repository)
            return CancelRequestEvidence(
                state=CancelRequestState.REQUESTED,
                control_id=control_id,
                task_id=task_id,
            )
