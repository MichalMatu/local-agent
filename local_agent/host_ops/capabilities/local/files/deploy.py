"""Copy one local artifact with explicit identity, durability steps and digest verification."""

from __future__ import annotations

import errno
import hashlib
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from .models import ArtifactDeploymentResult

_CHUNK_BYTES = 1024 * 1024
_UNSUPPORTED_DIRECTORY_FSYNC = {errno.EINVAL, errno.EBADF}
if hasattr(errno, "ENOTSUP"):
    _UNSUPPORTED_DIRECTORY_FSYNC.add(errno.ENOTSUP)


class ArtifactDeploymentError(RuntimeError):
    """Raised when artifact deployment cannot complete with trustworthy evidence."""


class LocalArtifactDeployer:
    """Deploy one regular file into an existing local directory and verify SHA-256."""

    def deploy(
        self,
        source: Path,
        destination_directory: Path,
        *,
        destination_name: str | None = None,
        replace: bool = False,
    ) -> ArtifactDeploymentResult:
        source_path = _regular_source(source)
        target_directory = _target_directory(destination_directory)
        target_name = _destination_name(
            source_path.name if destination_name is None else destination_name
        )
        destination = target_directory / target_name

        if destination.is_symlink():
            raise ArtifactDeploymentError("destination must not be a symbolic link")
        replaced_existing = destination.exists()
        if replaced_existing and not replace:
            raise ArtifactDeploymentError(
                f"destination already exists: {destination}; use explicit replace intent"
            )
        if replaced_existing and not destination.is_file():
            raise ArtifactDeploymentError(f"destination is not a regular file: {destination}")

        temporary_path: Path | None = None
        committed = False
        source_digest = hashlib.sha256()
        size_bytes = 0
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target_name}.hostops-",
                dir=target_directory,
            )
            temporary_path = Path(temporary_name)
            with source_path.open("rb") as source_file, os.fdopen(descriptor, "wb") as target_file:
                while True:
                    chunk = source_file.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    source_digest.update(chunk)
                    size_bytes += len(chunk)
                    target_file.write(chunk)
                target_file.flush()
                os.fsync(target_file.fileno())

            if destination.is_symlink():
                raise ArtifactDeploymentError(
                    "destination became a symbolic link during deployment"
                )
            if replace:
                if destination.exists() and not destination.is_file():
                    raise ArtifactDeploymentError(
                        "destination changed to a non-regular file during deployment"
                    )
                os.replace(temporary_path, destination)
            else:
                _commit_no_clobber(temporary_path, destination)
            committed = True
            temporary_path = None
            directory_synced = _sync_directory(target_directory)

            destination_digest, destination_size = _sha256_and_size(destination)
            expected_digest = source_digest.hexdigest()
            if destination_size != size_bytes or destination_digest != expected_digest:
                raise ArtifactDeploymentError(
                    "destination verification failed after commit; "
                    "destination may require operator cleanup"
                )
            return ArtifactDeploymentResult(
                source=source_path,
                destination=destination,
                size_bytes=size_bytes,
                sha256=expected_digest,
                replaced_existing=replaced_existing,
                directory_synced=directory_synced,
            )
        except ArtifactDeploymentError:
            raise
        except OSError as exc:
            state = "after commit" if committed else "before commit"
            raise ArtifactDeploymentError(f"artifact deployment failed {state}: {exc}") from exc
        finally:
            if temporary_path is not None:
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)


def _commit_no_clobber(temporary_path: Path, destination: Path) -> None:
    """Reserve an absent destination before replacing only our own reservation."""
    reservation_fd = -1
    reservation_identity: tuple[int, int] | None = None
    try:
        try:
            reservation_fd = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError as exc:
            raise ArtifactDeploymentError(
                "destination appeared during deployment; refusing overwrite"
            ) from exc
        reserved = os.fstat(reservation_fd)
        reservation_identity = (reserved.st_dev, reserved.st_ino)
        current = destination.lstat()
        if (current.st_dev, current.st_ino) != reservation_identity:
            raise ArtifactDeploymentError(
                "destination reservation changed during deployment; refusing overwrite"
            )
        os.replace(temporary_path, destination)
    finally:
        if reservation_fd >= 0:
            os.close(reservation_fd)
        if reservation_identity is not None and temporary_path.exists():
            with suppress(OSError):
                current = destination.lstat()
                if (current.st_dev, current.st_ino) == reservation_identity:
                    destination.unlink()


def _regular_source(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ArtifactDeploymentError("source must not be a symbolic link")
    try:
        resolved = expanded.resolve(strict=True)
    except OSError as exc:
        raise ArtifactDeploymentError(f"source cannot be resolved: {expanded}") from exc
    if not resolved.is_file():
        raise ArtifactDeploymentError(f"source is not a regular file: {resolved}")
    return resolved


def _target_directory(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ArtifactDeploymentError("destination directory must not be a symbolic link")
    try:
        resolved = expanded.resolve(strict=True)
    except OSError as exc:
        raise ArtifactDeploymentError(
            f"destination directory cannot be resolved: {expanded}"
        ) from exc
    if not resolved.is_dir():
        raise ArtifactDeploymentError(f"destination directory is not a directory: {resolved}")
    return resolved


def _destination_name(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        raise ArtifactDeploymentError("destination_name must be one plain filename")
    return value


def _sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size_bytes = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            size_bytes += len(chunk)
    return digest.hexdigest(), size_bytes


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
