from __future__ import annotations

import hashlib
import shlex
from pathlib import Path

import pytest

from local_agent.host_ops.capabilities.remote.ssh import (
    SYSTEM_SCP_EXECUTABLE,
    SshFileTransfer,
    SshTransferError,
)
from local_agent.host_ops.core.config import HostTarget
from local_agent.host_ops.core.execution import ProcessResult, ProcessState

_TEST_IDENTITY = "/tmp/host_ops_test_key"


def _result(stdout: str = "", *, exit_code: int = 0, stderr: str = "") -> ProcessResult:
    return ProcessResult(
        state=ProcessState.COMPLETED,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.001,
    )


def _target() -> HostTarget:
    return HostTarget(
        alias="phone",
        host="example.test",
        port=8022,
        user="user",
        identity_file=_TEST_IDENTITY,
    )


class FakeTransferRunner:
    def __init__(
        self,
        remote_files: dict[str, bytes] | None = None,
        *,
        corrupt_push: bool = False,
        hardlink_error: str | None = None,
        destination_appears_on_link: bytes | None = None,
    ) -> None:
        self.remote_files = dict(remote_files or {})
        self.remote_directories = {"/remote"}
        self.corrupt_push = corrupt_push
        self.hardlink_error = hardlink_error
        self.destination_appears_on_link = destination_appears_on_link
        self.scp_calls = 0
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, *, limits=None, **_kwargs):
        argv = tuple(command)
        self.commands.append(argv)
        if argv[0] == SYSTEM_SCP_EXECUTABLE:
            self.scp_calls += 1
            return self._scp(argv)
        return self._ssh(argv)

    def _scp(self, argv: tuple[str, ...]) -> ProcessResult:
        source, destination = argv[-2:]
        if ":/" in destination:
            remote_path = "/" + destination.split(":/", 1)[1]
            payload = Path(source).read_bytes()
            self.remote_files[remote_path] = payload + (b"corrupt" if self.corrupt_push else b"")
            return _result()
        remote_path = "/" + source.split(":/", 1)[1]
        Path(destination).write_bytes(self.remote_files[remote_path])
        return _result()

    def _ssh(self, argv: tuple[str, ...]) -> ProcessResult:
        remote = tuple(shlex.split(argv[-1]))
        program = remote[0]
        if program == "test":
            operator, path = remote[1], remote[2]
            if operator == "-L":
                return _result(exit_code=1)
            if operator == "-d":
                return _result(exit_code=0 if path in self.remote_directories else 1)
            if operator == "-e":
                return _result(exit_code=0 if path in self.remote_files else 1)
            if operator == "-f":
                return _result(exit_code=0 if path in self.remote_files else 1)
        if program == "wc":
            path = remote[-1]
            payload = self.remote_files[path]
            return _result(f"{len(payload)} {path}\n")
        if program == "sh":
            path = remote[-1]
            digest = hashlib.sha256(self.remote_files[path]).hexdigest()
            return _result(f"{digest}  {path}\n")
        if program == "ln":
            source, destination = remote[1], remote[2]
            if self.destination_appears_on_link is not None:
                self.remote_files[destination] = self.destination_appears_on_link
                return _result(exit_code=1, stderr="File exists")
            if self.hardlink_error is not None:
                return _result(exit_code=1, stderr=self.hardlink_error)
            if destination in self.remote_files:
                return _result(exit_code=1, stderr="File exists")
            self.remote_files[destination] = self.remote_files[source]
            return _result()
        if program == "mv":
            no_clobber = remote[1] == "-n"
            if no_clobber:
                source, destination = remote[2], remote[3]
                if destination in self.remote_files:
                    return _result()
            else:
                source, destination = remote[1], remote[2]
            self.remote_files[destination] = self.remote_files.pop(source)
            return _result()
        if program == "rm":
            self.remote_files.pop(remote[-1], None)
            return _result()
        raise AssertionError(f"unexpected remote command: {remote!r}")


def test_push_stages_verifies_and_commits_without_replace(tmp_path: Path) -> None:
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"firmware-data")
    runner = FakeTransferRunner()

    result = SshFileTransfer(runner).push(_target(), source, "/remote/firmware.bin")

    assert result.direction == "push"
    assert result.target == "phone"
    assert result.destination == "/remote/firmware.bin"
    assert result.size_bytes == len(b"firmware-data")
    assert result.sha256 == hashlib.sha256(b"firmware-data").hexdigest()
    assert result.replaced_existing is False
    assert result.staging_cleaned is True
    assert runner.remote_files["/remote/firmware.bin"] == b"firmware-data"
    assert not any(".hostops-upload-" in path for path in runner.remote_files)
    assert runner.scp_calls == 1


def test_push_falls_back_to_noclobber_rename_when_hardlinks_are_denied(
    tmp_path: Path,
) -> None:
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"firmware-data")
    runner = FakeTransferRunner(hardlink_error="Permission denied")

    result = SshFileTransfer(runner).push(_target(), source, "/remote/firmware.bin")

    assert result.replaced_existing is False
    assert result.staging_cleaned is True
    assert runner.remote_files["/remote/firmware.bin"] == b"firmware-data"
    assert not any(".hostops-upload-" in path for path in runner.remote_files)
    assert any(
        tuple(shlex.split(command[-1])[:2]) == ("mv", "-n")
        for command in runner.commands
        if command[0] != SYSTEM_SCP_EXECUTABLE
    )


def test_push_noclobber_fallback_preserves_destination_that_appears(
    tmp_path: Path,
) -> None:
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"firmware-data")
    runner = FakeTransferRunner(destination_appears_on_link=b"racer")

    with pytest.raises(SshTransferError, match="destination appeared"):
        SshFileTransfer(runner).push(_target(), source, "/remote/firmware.bin")

    assert runner.remote_files["/remote/firmware.bin"] == b"racer"
    assert not any(".hostops-upload-" in path for path in runner.remote_files)


def test_push_requires_explicit_replace_for_existing_remote_file(tmp_path: Path) -> None:
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"new")
    runner = FakeTransferRunner({"/remote/firmware.bin": b"old"})

    with pytest.raises(SshTransferError, match="explicit replace intent"):
        SshFileTransfer(runner).push(_target(), source, "/remote/firmware.bin")

    assert runner.remote_files["/remote/firmware.bin"] == b"old"
    assert runner.scp_calls == 0


def test_push_replace_is_verified_after_atomic_move(tmp_path: Path) -> None:
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"new")
    runner = FakeTransferRunner({"/remote/firmware.bin": b"old"})

    result = SshFileTransfer(runner).push(
        _target(),
        source,
        "/remote/firmware.bin",
        replace=True,
    )

    assert result.replaced_existing is True
    assert runner.remote_files["/remote/firmware.bin"] == b"new"


def test_push_rejects_corrupted_staging_and_cleans_it(tmp_path: Path) -> None:
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"payload")
    runner = FakeTransferRunner(corrupt_push=True)

    with pytest.raises(SshTransferError, match="staging file failed"):
        SshFileTransfer(runner).push(_target(), source, "/remote/firmware.bin")

    assert "/remote/firmware.bin" not in runner.remote_files
    assert not any(".hostops-upload-" in path for path in runner.remote_files)


def test_push_rejects_source_over_max_bytes(tmp_path: Path) -> None:
    source = tmp_path / "large.bin"
    source.write_bytes(b"12345")

    with pytest.raises(SshTransferError, match="exceeds max_bytes"):
        SshFileTransfer(FakeTransferRunner()).push(
            _target(),
            source,
            "/remote/large.bin",
            max_bytes=4,
        )


def test_push_rejects_directory_source_before_hashing(tmp_path: Path) -> None:
    source = tmp_path / "directory"
    source.mkdir()

    with pytest.raises(SshTransferError, match="local source is not a regular file"):
        SshFileTransfer(FakeTransferRunner()).push(
            _target(),
            source,
            "/remote/source.bin",
        )


def test_pull_stages_verifies_and_commits_locally(tmp_path: Path) -> None:
    payload = b"remote-result"
    runner = FakeTransferRunner({"/remote/result.bin": payload})
    destination = tmp_path / "result.bin"

    result = SshFileTransfer(runner).pull(_target(), "/remote/result.bin", destination)

    assert destination.read_bytes() == payload
    assert result.direction == "pull"
    assert result.destination == str(destination.resolve())
    assert result.sha256 == hashlib.sha256(payload).hexdigest()
    assert result.replaced_existing is False
    assert result.local_directory_synced is True
    assert runner.scp_calls == 1
    assert not list(tmp_path.glob(".hostops-download-*.tmp"))


def test_pull_requires_explicit_replace_for_existing_local_file(tmp_path: Path) -> None:
    runner = FakeTransferRunner({"/remote/result.bin": b"new"})
    destination = tmp_path / "result.bin"
    destination.write_bytes(b"old")

    with pytest.raises(SshTransferError, match="explicit replace intent"):
        SshFileTransfer(runner).pull(_target(), "/remote/result.bin", destination)

    assert destination.read_bytes() == b"old"
    assert runner.scp_calls == 0


def test_pull_replace_commits_verified_file(tmp_path: Path) -> None:
    runner = FakeTransferRunner({"/remote/result.bin": b"new"})
    destination = tmp_path / "result.bin"
    destination.write_bytes(b"old")

    result = SshFileTransfer(runner).pull(
        _target(),
        "/remote/result.bin",
        destination,
        replace=True,
    )

    assert destination.read_bytes() == b"new"
    assert result.replaced_existing is True


def test_pull_rejects_remote_file_over_max_bytes(tmp_path: Path) -> None:
    runner = FakeTransferRunner({"/remote/result.bin": b"12345"})

    with pytest.raises(SshTransferError, match="exceeds max_bytes"):
        SshFileTransfer(runner).pull(
            _target(),
            "/remote/result.bin",
            tmp_path / "result.bin",
            max_bytes=4,
        )

    assert runner.scp_calls == 0


@pytest.mark.parametrize(
    "path",
    ["relative.bin", "//remote/file.bin", "/remote/../secret", "/remote/file with space.bin"],
)
def test_transfer_rejects_unsafe_remote_paths(tmp_path: Path, path: str) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"data")

    with pytest.raises(SshTransferError, match="remote path"):
        SshFileTransfer(FakeTransferRunner()).push(_target(), source, path)
