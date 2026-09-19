from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import local_agent.foundation.core as core
from local_agent.foundation import storage
from local_agent.repository import admin
from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import MAX_TASK_FILE_BYTES, task_digest, validate_task
from local_agent.workflow import evidence
from local_agent.workflow.evidence import ChildEvidence

MAX_CONTROL_JSON_BYTES = MAX_TASK_FILE_BYTES
MAX_CONTROL_JSON_FILES = 4096
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,200}$")

OriginUrlFor = Callable[[RepositoryContext], str]


class WorkflowGitControlPlaneError(RuntimeError):
    """Base error for the unwired Git-backed workflow control plane."""


class WorkflowGitIntegrityError(WorkflowGitControlPlaneError):
    """Raised when checkout/remote/task identity conflicts with expected evidence."""


class WorkflowGitRepositoryBusyError(WorkflowGitControlPlaneError):
    """Raised when publication races unrelated repository work."""


class WorkflowGitPublicationConflict(WorkflowGitControlPlaneError):
    """Raised when a concurrent remote update prevents exact publication."""


class WorkflowGitPublicationAmbiguous(WorkflowGitControlPlaneError):
    """Raised when remote publication cannot be proven after a push failure."""


def _canonical_json_text(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def _canonical_task_id(value: Any) -> str:
    if not isinstance(value, str) or not _TASK_ID_RE.fullmatch(value):
        raise ValueError("workflow control-plane task id must be canonical bounded text")
    return value


def _canonical_origin(value: str) -> tuple[str, str]:
    raw = value.strip()
    if not raw:
        raise ValueError("Git origin must be non-empty")
    parsed = urlparse(raw)
    if parsed.scheme == "file":
        return ("file", str(Path(unquote(parsed.path)).expanduser().resolve()))
    if parsed.scheme == "" and (raw.startswith("/") or raw.startswith("~")):
        return ("file", str(Path(raw).expanduser().resolve()))
    normalized = admin.normalize_remote_url(raw)
    return ("remote", normalized.casefold())


def _require_success(result: dict[str, Any], operation: str) -> dict[str, Any]:
    if int(result.get("exit_code", 1)) != 0:
        raise WorkflowGitControlPlaneError(
            f"{operation} failed: {storage.git_failure_diagnostic(result)}"
        )
    return result


class GitWorkflowControlPlane:
    """Git-backed implementation of the workflow control-plane protocol.

    This adapter is deliberately not wired into supervisor/daemon code. It operates only
    on explicitly supplied RepositoryContext control checkouts. The default origin policy
    requires the configured GitHub repository; tests can inject an exact local bare origin.

    The adapter uses an inter-process flock under the control checkout's `.git` directory.
    The current Local Agent runtime does not yet share this lock, so production runtime
    wiring must not happen until control-Git locking is unified explicitly.
    """

    def __init__(
        self,
        *,
        origin_url_for: OriginUrlFor | None = None,
        process: Callable[..., dict[str, Any]] = core.process,
    ) -> None:
        self._origin_url_for = origin_url_for or admin.clone_url
        self._process = process

    @contextlib.contextmanager
    def _repository_lock(self, repository: RepositoryContext) -> Iterator[None]:
        control = repository.control.resolve()
        git_dir = control / ".git"
        if not git_dir.is_dir():
            raise WorkflowGitIntegrityError(
                f"workflow control checkout is not a normal Git clone: {control}"
            )
        lock_path = git_dir / "local-agent-workflow-control.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _git(
        self,
        repository: RepositoryContext,
        args: list[str],
        *,
        timeout: int = 120,
    ) -> dict[str, Any]:
        return self._process(
            ["git", *args],
            repository.control,
            timeout=timeout,
            log_commands=False,
        )

    def _network_git(
        self,
        repository: RepositoryContext,
        args: list[str],
        *,
        timeout: int = 120,
    ) -> dict[str, Any]:
        class _Runner:
            process = staticmethod(self._process)

        return storage.run_git_with_network_retry(
            _Runner,
            ["git", *args],
            repository.control,
            timeout=timeout,
            log_commands=False,
        )

    def _validate_origin(self, repository: RepositoryContext) -> None:
        result = _require_success(
            self._git(repository, ["remote", "get-url", "origin"], timeout=30),
            "read workflow control origin",
        )
        actual = _canonical_origin(str(result.get("output", "")))
        expected = _canonical_origin(self._origin_url_for(repository))
        if actual != expected:
            raise WorkflowGitIntegrityError(
                f"workflow control origin mismatch for {repository.repository_id!r}: "
                f"expected {expected[1]!r}, got {actual[1]!r}"
            )

    def _status_entries(self, repository: RepositoryContext) -> tuple[str, ...]:
        result = _require_success(
            self._git(
                repository,
                ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
                timeout=30,
            ),
            "read workflow control status",
        )
        return tuple(item for item in str(result.get("output", "")).split("\0") if item)

    def _require_clean(self, repository: RepositoryContext) -> None:
        entries = self._status_entries(repository)
        if entries:
            raise WorkflowGitIntegrityError(
                "workflow control checkout has unexpected local changes: "
                + ", ".join(entries[:20])
            )

    def _ensure_branch(self, repository: RepositoryContext) -> None:
        branch = self._git(
            repository,
            ["symbolic-ref", "--quiet", "--short", "HEAD"],
            timeout=30,
        )
        current = str(branch.get("output", "")).strip() if branch["exit_code"] == 0 else ""
        if current == repository.control_branch:
            return
        _require_success(
            self._git(
                repository,
                ["checkout", repository.control_branch],
                timeout=60,
            ),
            "checkout workflow control branch",
        )

    def _require_remote_exact(self, repository: RepositoryContext) -> None:
        remote_ref = f"refs/remotes/origin/{repository.control_branch}"
        result = _require_success(
            self._git(
                repository,
                ["rev-list", "--left-right", "--count", f"HEAD...{remote_ref}"],
                timeout=30,
            ),
            "compare workflow control HEAD with remote",
        )
        parts = str(result.get("output", "")).split()
        if len(parts) != 2:
            raise WorkflowGitIntegrityError("invalid workflow control divergence output")
        try:
            ahead, behind = (int(parts[0]), int(parts[1]))
        except ValueError as exc:
            raise WorkflowGitIntegrityError("invalid workflow control divergence count") from exc
        if ahead != 0 or behind != 0:
            raise WorkflowGitIntegrityError(
                f"workflow control checkout is not exact remote state: ahead={ahead} behind={behind}"
            )

    def _sync_locked(self, repository: RepositoryContext) -> None:
        control = repository.control.resolve()
        if not control.is_dir() or not (control / ".git").is_dir():
            raise WorkflowGitIntegrityError(
                f"workflow control checkout missing: {repository.control}"
            )
        self._validate_origin(repository)
        self._require_clean(repository)
        self._ensure_branch(repository)
        self._require_clean(repository)
        pull = self._network_git(
            repository,
            storage.bounded_control_pull_args(repository.control_branch),
            timeout=120,
        )
        _require_success(pull, "synchronize workflow control branch")
        self._require_clean(repository)
        self._require_remote_exact(repository)

    def _safe_path(self, repository: RepositoryContext, relative: str) -> Path:
        root = repository.control.resolve()
        target = (root / relative).resolve()
        if root not in target.parents:
            raise WorkflowGitIntegrityError(
                f"workflow control path escapes checkout: {relative!r}"
            )
        return target

    def _read_json_path(
        self,
        repository: RepositoryContext,
        relative: str,
    ) -> dict[str, Any] | None:
        path = self._safe_path(repository, relative)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise WorkflowGitIntegrityError(
                f"workflow control evidence path is not a regular file: {relative}"
            )
        raw = path.read_bytes()
        if len(raw) > MAX_CONTROL_JSON_BYTES:
            raise WorkflowGitIntegrityError(
                f"workflow control evidence exceeds bounds: {relative}"
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowGitIntegrityError(
                f"invalid workflow control JSON: {relative}"
            ) from exc
        if not isinstance(payload, dict):
            raise WorkflowGitIntegrityError(
                f"workflow control JSON must contain an object: {relative}"
            )
        return payload

    def _json_payloads(
        self,
        repository: RepositoryContext,
        relative_directory: str,
    ) -> list[dict[str, Any]]:
        directory = self._safe_path(repository, relative_directory)
        if not directory.exists():
            return []
        if directory.is_symlink() or not directory.is_dir():
            raise WorkflowGitIntegrityError(
                f"workflow control evidence directory is invalid: {relative_directory}"
            )
        paths = sorted(path for path in directory.glob("*.json") if path.is_file())
        if len(paths) > MAX_CONTROL_JSON_FILES:
            raise WorkflowGitIntegrityError(
                f"workflow control evidence file count exceeds {MAX_CONTROL_JSON_FILES}"
            )
        payloads: list[dict[str, Any]] = []
        for path in paths:
            relative = path.relative_to(repository.control.resolve()).as_posix()
            payload = self._read_json_path(repository, relative)
            assert payload is not None
            payloads.append(payload)
        return payloads

    def _inspect_locked(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_digest: str,
    ) -> ChildEvidence:
        task_id = _canonical_task_id(task_id)
        return evidence.classify_child_evidence(
            task_payload=self._read_json_path(
                repository,
                f".agent/tasks/{task_id}.json",
            ),
            status_payload=self._read_json_path(repository, ".agent/status/daemon.json"),
            result_payload=self._read_json_path(
                repository,
                f".agent/results/{task_id}.json",
            ),
            expected_task_id=task_id,
            expected_digest=expected_digest,
        )

    def inspect_child(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_digest: str,
    ) -> ChildEvidence:
        with self._repository_lock(repository):
            self._sync_locked(repository)
            return self._inspect_locked(repository, task_id, expected_digest)

    def _has_unrelated_work_locked(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool:
        child_task_id = _canonical_task_id(child_task_id)
        tasks = self._json_payloads(repository, ".agent/tasks")
        results = {
            str(payload["id"]): payload
            for payload in self._json_payloads(repository, ".agent/results")
            if isinstance(payload.get("id"), str) and payload["id"]
        }
        return evidence.has_unrelated_work(
            child_task_id=child_task_id,
            status_payload=self._read_json_path(repository, ".agent/status/daemon.json"),
            task_payloads=tasks,
            result_payloads=results,
        )

    def has_unrelated_work(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool:
        with self._repository_lock(repository):
            self._sync_locked(repository)
            return self._has_unrelated_work_locked(repository, child_task_id)

    def _write_task_create_only(
        self,
        repository: RepositoryContext,
        task: dict[str, Any],
    ) -> str:
        task_id = _canonical_task_id(task["id"])
        relative = f".agent/tasks/{task_id}.json"
        target = self._safe_path(repository, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = _canonical_json_text(task).encode("utf-8")
        if len(encoded) > MAX_TASK_FILE_BYTES:
            raise WorkflowGitIntegrityError(
                f"workflow child task exceeds {MAX_TASK_FILE_BYTES} bytes"
            )
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise WorkflowGitIntegrityError(
                f"workflow child task appeared concurrently: {task_id}"
            ) from exc
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return relative

    def _reset_to(self, repository: RepositoryContext, commit: str) -> None:
        _require_success(
            self._git(repository, ["reset", "--hard", commit], timeout=60),
            "restore workflow control checkout",
        )
        self._require_clean(repository)

    def _fetch_remote(self, repository: RepositoryContext) -> dict[str, Any]:
        remote_ref = f"refs/remotes/origin/{repository.control_branch}"
        return self._network_git(
            repository,
            [
                "fetch",
                "--depth",
                str(storage.CONTROL_HISTORY_DEPTH),
                "--no-tags",
                "origin",
                f"+refs/heads/{repository.control_branch}:{remote_ref}",
            ],
            timeout=120,
        )

    def _remote_task_payload(
        self,
        repository: RepositoryContext,
        task_id: str,
    ) -> dict[str, Any] | None:
        task_id = _canonical_task_id(task_id)
        remote_ref = f"refs/remotes/origin/{repository.control_branch}"
        relative = f".agent/tasks/{task_id}.json"
        result = self._git(
            repository,
            ["show", f"{remote_ref}:{relative}"],
            timeout=30,
        )
        if result["exit_code"] != 0:
            return None
        text = str(result.get("output", ""))
        if len(text.encode("utf-8")) > MAX_TASK_FILE_BYTES:
            raise WorkflowGitIntegrityError("remote workflow child task exceeds bounds")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise WorkflowGitIntegrityError("remote workflow child task is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise WorkflowGitIntegrityError("remote workflow child task must be an object")
        return payload

    def _recover_failed_push(
        self,
        repository: RepositoryContext,
        task: dict[str, Any],
        *,
        base_head: str,
        push_result: dict[str, Any],
    ) -> None:
        task_id = str(task["id"])
        expected_digest = task_digest(task)
        # Never leave an unproven local-only publication behind. If the push actually
        # succeeded but its response was lost, a fresh fetch below will recover proof.
        self._reset_to(repository, base_head)
        fetch = self._fetch_remote(repository)
        if fetch["exit_code"] != 0:
            raise WorkflowGitPublicationAmbiguous(
                "workflow child push failed and remote publication could not be proven: "
                + storage.git_failure_diagnostic(push_result)
            )
        remote_ref = f"refs/remotes/origin/{repository.control_branch}"
        remote_task = self._remote_task_payload(repository, task_id)
        _require_success(
            self._git(repository, ["reset", "--hard", remote_ref], timeout=60),
            "align workflow control checkout after failed push",
        )
        self._require_clean(repository)
        if remote_task is not None:
            try:
                remote_digest = task_digest(remote_task)
            except Exception as exc:
                raise WorkflowGitIntegrityError(
                    "remote workflow child task cannot be digested"
                ) from exc
            if remote_task.get("id") != task_id or remote_digest != expected_digest:
                raise WorkflowGitIntegrityError(
                    f"remote workflow child identity mismatch after failed push: {task_id}"
                )
            return
        raise WorkflowGitPublicationConflict(
            "workflow child push did not publish the expected task; remote changed concurrently"
        )

    def _push_control_branch(self, repository: RepositoryContext) -> dict[str, Any]:
        return self._network_git(
            repository,
            ["push", "origin", repository.control_branch],
            timeout=120,
        )

    def publish_child(
        self,
        repository: RepositoryContext,
        task: dict[str, Any],
    ) -> None:
        validate_task(task, require_agent_binding=True)
        task_id = _canonical_task_id(task.get("id"))
        expected_digest = task_digest(task)

        with self._repository_lock(repository):
            self._sync_locked(repository)
            existing = self._inspect_locked(repository, task_id, expected_digest)
            if existing.kind != evidence.ChildEvidenceKind.ABSENT:
                if (
                    existing.kind != evidence.ChildEvidenceKind.DIGEST_MISMATCH
                    and existing.task_digest == expected_digest
                ):
                    return
                raise WorkflowGitIntegrityError(
                    f"workflow child task id already exists with conflicting evidence: {task_id}"
                )
            if self._has_unrelated_work_locked(repository, task_id):
                raise WorkflowGitRepositoryBusyError(
                    f"repository {repository.repository_id!r} gained unrelated work before publication"
                )

            head = _require_success(
                self._git(repository, ["rev-parse", "HEAD"], timeout=30),
                "read workflow control HEAD",
            )
            base_head = str(head.get("output", "")).strip()
            relative = self._write_task_create_only(repository, task)
            try:
                _require_success(
                    self._git(repository, ["add", "--", relative], timeout=30),
                    "stage workflow child task",
                )
                staged = self._git(
                    repository,
                    ["diff", "--cached", "--name-only"],
                    timeout=30,
                )
                _require_success(staged, "inspect staged workflow publication")
                staged_paths = tuple(
                    line.strip()
                    for line in str(staged.get("output", "")).splitlines()
                    if line.strip()
                )
                if staged_paths != (relative,):
                    raise WorkflowGitIntegrityError(
                        f"workflow publication staged unexpected paths: {staged_paths!r}"
                    )
                _require_success(
                    self._git(
                        repository,
                        [
                            "commit",
                            "-m",
                            f"Queue workflow child {task_id}",
                            "--",
                            relative,
                        ],
                        timeout=60,
                    ),
                    "commit workflow child task",
                )
            except Exception:
                self._reset_to(repository, base_head)
                raise

            push = self._push_control_branch(repository)
            if push["exit_code"] != 0:
                self._recover_failed_push(
                    repository,
                    task,
                    base_head=base_head,
                    push_result=push,
                )
                return
            self._require_clean(repository)
