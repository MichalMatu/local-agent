from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import local_agent.host_ops.capabilities.local.files.inspect as inspect_module
from local_agent.host_ops.capabilities.local.files import ArtifactInspectionError, LocalArtifactInspector


def test_inspect_reports_digest_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "artifact.bin"
    source.write_bytes(b"artifact-data")

    result = LocalArtifactInspector().inspect(source)

    assert result.requested_path == source.absolute()
    assert result.real_path == source.resolve()
    assert result.file_type == "regular_file"
    assert result.size_bytes == len(b"artifact-data")
    assert result.sha256 == hashlib.sha256(b"artifact-data").hexdigest()
    assert result.modified_time_ns == source.stat().st_mtime_ns
    assert result.as_dict()["real_path"] == str(source.resolve())


def test_inspect_rejects_symlink(tmp_path: Path) -> None:
    source = tmp_path / "artifact.bin"
    source.write_bytes(b"data")
    link = tmp_path / "artifact-link.bin"
    link.symlink_to(source)

    with pytest.raises(ArtifactInspectionError, match="must not be a symbolic link"):
        LocalArtifactInspector().inspect(link)


def test_inspect_rejects_path_replacement_after_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "artifact.bin"
    source.write_bytes(b"original")
    replacement = tmp_path / "replacement.bin"
    replacement.write_bytes(b"replacement")
    original_hash = inspect_module._sha256_fd

    def replace_path(descriptor: int) -> str:
        source.unlink()
        source.symlink_to(replacement)
        return original_hash(descriptor)

    monkeypatch.setattr(inspect_module, "_sha256_fd", replace_path)

    with pytest.raises(ArtifactInspectionError, match=r"artifact (changed|became)"):
        LocalArtifactInspector().inspect(source)


def test_inspect_rejects_non_regular_file(tmp_path: Path) -> None:
    directory = tmp_path / "artifact-dir"
    directory.mkdir()

    with pytest.raises(ArtifactInspectionError, match="not a regular file"):
        LocalArtifactInspector().inspect(directory)


def test_inspect_reports_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.bin"

    with pytest.raises(ArtifactInspectionError, match="could not inspect artifact"):
        LocalArtifactInspector().inspect(missing)
