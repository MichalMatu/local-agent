"""Bounded verified file transfer over the configured OpenSSH transport."""

from __future__ import annotations

import errno
import hashlib
import os
import re
import secrets
import stat
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from local_agent.host_ops.core.config import HostTarget
from local_agent.host_ops.core.execution import ExecutionLimits, ProcessResult, ProcessRunner, ProcessState

from .client import SshClient
from .command import SshOptions, build_scp_pull_command, build_scp_push_command
from .paths import normalize_remote_file_path

DEFAULT_MAX_TRANSFER_BYTES = 512 * 1024 * 1024
MAX_TRANSFER_BYTES = 16 * 1024 * 1024 * 1024
_HASH_CHUNK_BYTES = 1024 * 1024
_SHA256_PATTERN = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
_UNSUPPORTED_DIRECTORY_FSYNC = {errno.EINVAL, errno.EBADF}
if hasattr(errno, "ENOTSUP"):
    _UNSUPPORTED_DIRECTORY_FSYNC.add(errno.ENOTSUP)
_REMOTE_HASH_SCRIPT = (
    'if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; '
    'elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1"; '
    'elif command -v openssl >/dev/null 2>&1; then openssl dgst -sha256 "$1"; '
    "else printf '%s\\n' 'no SHA-256 tool available' >&2; exit 127; fi"
)


class SshTransferError(RuntimeError):
    """Raised when a verified SSH file transfer cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class SshTransferResult:
    direction: str
    target: str
    source: str
    destination: str
    size_bytes: int
    sha256: str
    replaced_existing: bool
    staging_cleaned: bool = True
    local_directory_synced: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "target": self.target,
            "source": self.source,
            "destination": self.destination,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "replaced_existing": self.replaced_existing,
            "staging_cleaned": self.staging_cleaned,
            "local_directory_synced": self.local_directory_synced,
        }


class SshFileTransfer:
    def __init__(
        self,
        runner: ProcessRunner | None = None,
        *,
        options: SshOptions | None = None,
    ) -> None:
        self._runner = runner or ProcessRunner()
        self._options = options or SshOptions()
        self._client = SshClient(self._runner, options=self._options)

    def push(
        self,
        target: HostTarget,
        local_source: Path,
        remote_destination: str,
        *,
        replace: bool = False,
        max_bytes: int = DEFAULT_MAX_TRANSFER_BYTES,
        limits: ExecutionLimits | None = None,
    ) -> SshTransferResult:
        maximum = _validate_max_bytes(max_bytes)
        budget = _TransferBudget(limits or ExecutionLimits(timeout_seconds=300.0))
        source = _inspect_local_source(local_source, maximum)
        destination = _validated_remote_path(remote_destination)
        parent = str(PurePosixPath(destination).parent)
        self._require_remote_directory(target, parent, budget)
        replaced_existing = self._validate_remote_destination(
            target,
            destination,
            replace=replace,
            budget=budget,
        )
        stage = str(PurePosixPath(parent) / f".hostops-upload-{secrets.token_hex(12)}.tmp")
        stage_present = False

        try:
            command = build_scp_push_command(target, source.path, stage, options=self._options)
            self._require_process_ok(
                self._runner.run(command, limits=budget.remaining()),
                "SCP upload",
            )
            stage_present = True
            remote_size = self._remote_size(target, stage, budget)
            remote_sha256 = self._remote_sha256(target, stage, budget)
            if remote_size != source.size_bytes or remote_sha256 != source.sha256:
                raise SshTransferError("uploaded staging file failed size or SHA-256 verification")
            if _sha256_file(source.path) != source.sha256:
                raise SshTransferError("local source changed while upload was in progress")

            if replace:
                self._require_remote_ok(
                    target, ("mv", stage, destination), budget, "remote replace"
                )
                stage_present = False
            else:
                stage_present = not _commit_remote_no_clobber(
                    self._client,
                    target,
                    stage,
                    destination,
                    budget,
                )

            final_size = self._remote_size(target, destination, budget)
            final_sha256 = self._remote_sha256(target, destination, budget)
            if final_size != source.size_bytes or final_sha256 != source.sha256:
                raise SshTransferError("remote destination failed post-commit verification")

            staging_cleaned = True
            if stage_present:
                staging_cleaned = self._cleanup_remote_stage(target, stage, budget)
                stage_present = not staging_cleaned
            return SshTransferResult(
                direction="push",
                target=target.alias,
                source=str(source.path),
                destination=destination,
                size_bytes=source.size_bytes,
                sha256=source.sha256,
                replaced_existing=replaced_existing,
                staging_cleaned=staging_cleaned,
            )
        except (OSError, SshTransferError, ValueError) as exc:
            if stage_present:
                self._cleanup_remote_stage(target, stage, budget, best_effort=True)
            if isinstance(exc, SshTransferError):
                raise
            raise SshTransferError(str(exc)) from exc

    def pull(
        self,
        target: HostTarget,
        remote_source: str,
        local_destination: Path,
        *,
        replace: bool = False,
        max_bytes: int = DEFAULT_MAX_TRANSFER_BYTES,
        limits: ExecutionLimits | None = None,
    ) -> SshTransferResult:
        maximum = _validate_max_bytes(max_bytes)
        budget = _TransferBudget(limits or ExecutionLimits(timeout_seconds=300.0))
        source = _validated_remote_path(remote_source)
        self._require_remote_regular_file(target, source, budget)
        remote_size = self._remote_size(target, source, budget)
        if remote_size > maximum:
            raise SshTransferError(f"remote source exceeds max_bytes ({remote_size} > {maximum})")
        remote_sha256 = self._remote_sha256(target, source, budget)
        destination, replaced_existing = _prepare_local_destination(
            local_destination, replace=replace
        )
        stage = destination.parent / f".hostops-download-{secrets.token_hex(12)}.tmp"

        try:
            command = build_scp_pull_command(target, source, stage, options=self._options)
            self._require_process_ok(
                self._runner.run(command, limits=budget.remaining()),
                "SCP download",
            )
            staged = _inspect_local_source(stage, maximum)
            if staged.size_bytes != remote_size or staged.sha256 != remote_sha256:
                raise SshTransferError(
                    "downloaded staging file failed size or SHA-256 verification"
                )
            _fsync_file(stage)
            if replace:
                os.replace(stage, destination)
            else:
                try:
                    os.link(stage, destination)
                except FileExistsError as exc:
                    raise SshTransferError(
                        "local destination appeared during no-clobber commit"
                    ) from exc
                except OSError as exc:
                    raise SshTransferError(f"local no-clobber commit failed: {exc}") from exc
                stage.unlink()
            directory_synced = _sync_directory(destination.parent)
            return SshTransferResult(
                direction="pull",
                target=target.alias,
                source=source,
                destination=str(destination),
                size_bytes=remote_size,
                sha256=remote_sha256,
                replaced_existing=replaced_existing,
                local_directory_synced=directory_synced,
            )
        except OSError as exc:
            raise SshTransferError(str(exc)) from exc
        finally:
            if stage.exists() or stage.is_symlink():
                stage.unlink(missing_ok=True)

    def _require_remote_directory(
        self,
        target: HostTarget,
        path: str,
        budget: _TransferBudget,
    ) -> None:
        if self._remote_test(target, "-L", path, budget):
            raise SshTransferError("remote destination directory must not be a symbolic link")
        if not self._remote_test(target, "-d", path, budget):
            raise SshTransferError("remote destination directory does not exist")

    def _validate_remote_destination(
        self,
        target: HostTarget,
        path: str,
        *,
        replace: bool,
        budget: _TransferBudget,
    ) -> bool:
        symlink = self._remote_test(target, "-L", path, budget)
        exists = symlink or self._remote_test(target, "-e", path, budget)
        if not exists:
            return False
        if symlink:
            raise SshTransferError("remote destination must not be a symbolic link")
        if not self._remote_test(target, "-f", path, budget):
            raise SshTransferError("remote destination exists and is not a regular file")
        if not replace:
            raise SshTransferError("remote destination exists; explicit replace intent is required")
        return True

    def _require_remote_regular_file(
        self,
        target: HostTarget,
        path: str,
        budget: _TransferBudget,
    ) -> None:
        if self._remote_test(target, "-L", path, budget):
            raise SshTransferError("remote source must not be a symbolic link")
        if not self._remote_test(target, "-f", path, budget):
            raise SshTransferError("remote source is not a regular file")

    def _remote_test(
        self,
        target: HostTarget,
        operator: str,
        path: str,
        budget: _TransferBudget,
    ) -> bool:
        return _remote_test(self._client, target, operator, path, budget)

    def _remote_size(self, target: HostTarget, path: str, budget: _TransferBudget) -> int:
        result = self._require_remote_ok(target, ("wc", "-c", path), budget, "remote size")
        try:
            size = int(result.stdout.strip().split()[0])
        except (IndexError, ValueError) as exc:
            raise SshTransferError("remote size command returned invalid output") from exc
        if size < 0:
            raise SshTransferError("remote size command returned a negative size")
        return size

    def _remote_sha256(self, target: HostTarget, path: str, budget: _TransferBudget) -> str:
        result = self._require_remote_ok(
            target,
            ("sh", "-c", _REMOTE_HASH_SCRIPT, "hostops-sha256", path),
            budget,
            "remote SHA-256",
        )
        match = _SHA256_PATTERN.search(result.stdout)
        if match is None:
            raise SshTransferError("remote SHA-256 command returned invalid output")
        return match.group(0).lower()

    def _require_remote_ok(
        self,
        target: HostTarget,
        argv: tuple[str, ...],
        budget: _TransferBudget,
        context: str,
    ) -> ProcessResult:
        result = self._client.execute(target, argv, limits=budget.remaining())
        self._require_process_ok(result, context)
        return result

    def _cleanup_remote_stage(
        self,
        target: HostTarget,
        stage: str,
        budget: _TransferBudget,
        *,
        best_effort: bool = False,
    ) -> bool:
        try:
            result = self._client.execute(target, ("rm", "-f", stage), limits=budget.remaining())
        except SshTransferError:
            if best_effort:
                return False
            raise
        if result.ok:
            return True
        if best_effort:
            return False
        raise SshTransferError(_process_failure("remote staging cleanup", result))

    @staticmethod
    def _require_process_ok(result: ProcessResult, context: str) -> None:
        if not result.ok:
            raise SshTransferError(_process_failure(context, result))


def _commit_remote_no_clobber(
    client: SshClient,
    target: HostTarget,
    stage: str,
    destination: str,
    budget: _TransferBudget,
) -> bool:
    link_result = client.execute(
        target,
        ("ln", stage, destination),
        limits=budget.remaining(),
    )
    if link_result.ok:
        return False
    if link_result.state is not ProcessState.COMPLETED:
        raise SshTransferError(
            _process_failure("remote no-clobber hard-link commit", link_result)
        )

    # Android/Termux can deny hard links for an SCP-uploaded staging file.
    # A successful mv -n consumes the stage; a no-clobber no-op leaves it in place.
    move_result = client.execute(
        target,
        ("mv", "-n", stage, destination),
        limits=budget.remaining(),
    )
    if move_result.state is not ProcessState.COMPLETED:
        raise SshTransferError(
            _process_failure("remote no-clobber rename fallback", move_result)
        )
    if not _remote_test(client, target, "-e", stage, budget):
        return True
    if _remote_test(client, target, "-e", destination, budget):
        raise SshTransferError("remote destination appeared during no-clobber commit")
    if not move_result.ok:
        raise SshTransferError(
            _process_failure("remote no-clobber rename fallback", move_result)
        )
    raise SshTransferError(
        "remote no-clobber rename fallback left the staging file in place"
    )


def _remote_test(
    client: SshClient,
    target: HostTarget,
    operator: str,
    path: str,
    budget: _TransferBudget,
) -> bool:
    result = client.execute(target, ("test", operator, path), limits=budget.remaining())
    if result.state is not ProcessState.COMPLETED:
        raise SshTransferError(_process_failure("remote test", result))
    if result.exit_code == 0:
        return True
    if result.exit_code == 1:
        return False
    raise SshTransferError(_process_failure("remote test", result))


@dataclass(frozen=True, slots=True)
class _LocalSource:
    path: Path
    size_bytes: int
    sha256: str


class _TransferBudget:
    def __init__(self, limits: ExecutionLimits) -> None:
        self._limits = limits
        self._deadline = time.monotonic() + limits.timeout_seconds

    def remaining(self) -> ExecutionLimits:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise SshTransferError("file transfer exceeded its whole-operation timeout")
        return ExecutionLimits(
            timeout_seconds=remaining,
            terminate_grace_seconds=self._limits.terminate_grace_seconds,
            pipe_drain_seconds=self._limits.pipe_drain_seconds,
            max_stdout_bytes=self._limits.max_stdout_bytes,
            max_stderr_bytes=self._limits.max_stderr_bytes,
        )


def _inspect_local_source(path: Path, max_bytes: int) -> _LocalSource:
    source = Path(path).expanduser()
    if source.is_symlink():
        raise SshTransferError("local source must not be a symbolic link")
    try:
        resolved = source.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise SshTransferError(f"could not inspect local source: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise SshTransferError("local source is not a regular file")
    if metadata.st_size > max_bytes:
        raise SshTransferError(f"local source exceeds max_bytes ({metadata.st_size} > {max_bytes})")
    try:
        digest = _sha256_file(resolved)
    except OSError as exc:
        raise SshTransferError(f"could not hash local source: {exc}") from exc
    return _LocalSource(resolved, metadata.st_size, digest)


def _prepare_local_destination(path: Path, *, replace: bool) -> tuple[Path, bool]:
    requested = Path(path).expanduser()
    parent = requested.parent
    if parent.is_symlink():
        raise SshTransferError("local destination directory must not be a symbolic link")
    try:
        resolved_parent = parent.resolve(strict=True)
    except OSError as exc:
        raise SshTransferError(f"could not resolve local destination directory: {exc}") from exc
    if not resolved_parent.is_dir():
        raise SshTransferError("local destination parent is not a directory")
    destination = resolved_parent / requested.name
    if destination.is_symlink():
        raise SshTransferError("local destination must not be a symbolic link")
    exists = destination.exists()
    if exists and not destination.is_file():
        raise SshTransferError("local destination exists and is not a regular file")
    if exists and not replace:
        raise SshTransferError("local destination exists; explicit replace intent is required")
    return destination, exists


def _validated_remote_path(path: str) -> str:
    try:
        return normalize_remote_file_path(path)
    except ValueError as exc:
        raise SshTransferError(str(exc)) from exc


def _validate_max_bytes(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_TRANSFER_BYTES
    ):
        raise SshTransferError(f"max_bytes must be an integer in range 1..{MAX_TRANSFER_BYTES}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _sync_directory(path: Path) -> bool:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            if exc.errno in _UNSUPPORTED_DIRECTORY_FSYNC:
                return False
            raise
    finally:
        os.close(descriptor)
    return True


def _process_failure(context: str, result: ProcessResult) -> str:
    detail = result.error or result.stderr.strip() or f"exit status {result.exit_code}"
    return f"{context} failed: {detail}"
