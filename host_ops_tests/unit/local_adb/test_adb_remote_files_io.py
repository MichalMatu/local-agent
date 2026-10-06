from __future__ import annotations

from pathlib import Path

import pytest

from local_agent.host_ops.capabilities.local.adb.remote_files import AdbRemoteFiles, AdbTransferError
from local_agent.host_ops.core.execution import ExecutionLimits, ProcessResult, ProcessState

ADB = "/opt/android/platform-tools/adb"
SERIAL = "ABC123"


class FakeRunner:
    def __init__(self, *results: ProcessResult) -> None:
        self.results = list(results)
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, *, limits=None):
        self.commands.append(tuple(command))
        return self.results.pop(0)


def _result(
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    stdout_truncated: bool = False,
) -> ProcessResult:
    return ProcessResult(
        state=ProcessState.COMPLETED,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        stdout_truncated=stdout_truncated,
    )


def _remote(runner: FakeRunner, provider=None) -> AdbRemoteFiles:
    limits = provider or (lambda: ExecutionLimits(timeout_seconds=5.0))
    return AdbRemoteFiles(runner, ADB, SERIAL, limits)


def test_push_and_pull_use_explicit_serial_and_literal_paths(tmp_path: Path) -> None:
    runner = FakeRunner(_result(), _result())
    remote = _remote(runner)
    source = tmp_path / "input.bin"
    source.write_bytes(b"payload")
    destination = tmp_path / "out.bin"

    remote.push(source, "/sdcard/input.bin")
    remote.pull("/sdcard/out.bin", destination)

    assert runner.commands == [
        (ADB, "-s", SERIAL, "push", str(source), "/sdcard/input.bin"),
        (ADB, "-s", SERIAL, "pull", "/sdcard/out.bin", str(destination)),
    ]


def test_push_and_pull_propagate_bounded_process_failures(tmp_path: Path) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(b"payload")

    with pytest.raises(AdbTransferError, match="truncated"):
        _remote(FakeRunner(_result(stdout_truncated=True))).push(source, "/sdcard/input.bin")

    with pytest.raises(AdbTransferError, match="ADB pull"):
        _remote(FakeRunner(_result(stderr="permission denied", exit_code=1))).pull(
            "/data/private.bin",
            tmp_path / "out.bin",
        )


def test_cleanup_handles_exhausted_budget_in_best_effort_mode() -> None:
    def exhausted() -> ExecutionLimits:
        raise AdbTransferError("deadline exhausted")

    remote = _remote(FakeRunner(), exhausted)

    assert remote.cleanup("/sdcard/.tmp", best_effort=True) is False
    with pytest.raises(AdbTransferError, match="deadline exhausted"):
        remote.cleanup("/sdcard/.tmp")


def test_remote_test_exit_one_with_diagnostics_is_not_treated_as_false() -> None:
    remote = _remote(FakeRunner(_result(stderr="device disconnected", exit_code=1)))

    with pytest.raises(AdbTransferError, match="device disconnected"):
        remote.require_directory("/sdcard")
