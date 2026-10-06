from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from local_agent.host_ops.capabilities.local.adb.remote_files import (
    AdbRemoteFiles,
    AdbTransferError,
    normalize_remote_file_path,
)
from local_agent.host_ops.core.execution import ExecutionLimits, ProcessResult, ProcessState

ADB = "/opt/android/platform-tools/adb"
SERIAL = "ABC123"
DIGEST = "a" * 64
_REMOTE_SEGMENT = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._@%+=,-",
    min_size=1,
    max_size=24,
).filter(lambda value: value not in {".", ".."})


class FakeRunner:
    def __init__(self, *results: ProcessResult) -> None:
        self.results = list(results)
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, *, limits=None):
        self.commands.append(tuple(command))
        return self.results.pop(0)


def _result(
    stdout: str = "",
    *,
    stderr: str = "",
    exit_code: int = 0,
    state: ProcessState = ProcessState.COMPLETED,
    stdout_truncated: bool = False,
) -> ProcessResult:
    return ProcessResult(
        state=state,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        stdout_truncated=stdout_truncated,
    )


def _remote(runner: FakeRunner) -> AdbRemoteFiles:
    return AdbRemoteFiles(
        runner,
        ADB,
        SERIAL,
        lambda: ExecutionLimits(timeout_seconds=5.0),
    )


def _false_test() -> ProcessResult:
    return _result(exit_code=1)


def test_require_ready_uses_explicit_serial() -> None:
    runner = FakeRunner(_result("device\n"))

    _remote(runner).require_ready()

    assert runner.commands == [(ADB, "-s", SERIAL, "get-state")]


def test_require_ready_rejects_non_device_state() -> None:
    with pytest.raises(AdbTransferError, match="not ready"):
        _remote(FakeRunner(_result("offline\n"))).require_ready()


def test_require_directory_rejects_symlink_and_missing_directory() -> None:
    with pytest.raises(AdbTransferError, match="symbolic link"):
        _remote(
            FakeRunner(
                _result(),
            )
        ).require_directory("/sdcard/tmp")

    with pytest.raises(AdbTransferError, match="does not exist"):
        _remote(FakeRunner(_false_test(), _false_test())).require_directory("/sdcard/tmp")


def test_validate_destination_accepts_absent_and_explicit_replace() -> None:
    absent = _remote(FakeRunner(_false_test(), _false_test()))
    assert absent.validate_destination("/sdcard/file.bin", replace=False) is False

    existing = _remote(FakeRunner(_false_test(), _result(), _result()))
    assert existing.validate_destination("/sdcard/file.bin", replace=True) is True


def test_validate_destination_rejects_symlink_nonfile_and_no_replace() -> None:
    with pytest.raises(AdbTransferError, match="symbolic link"):
        _remote(FakeRunner(_result())).validate_destination("/sdcard/file.bin", replace=True)

    with pytest.raises(AdbTransferError, match="not a regular file"):
        _remote(FakeRunner(_false_test(), _result(), _false_test())).validate_destination(
            "/sdcard/file.bin", replace=True
        )

    with pytest.raises(AdbTransferError, match="replace intent"):
        _remote(FakeRunner(_false_test(), _result(), _result())).validate_destination(
            "/sdcard/file.bin", replace=False
        )


def test_require_regular_file_rejects_symlink_and_missing_file() -> None:
    with pytest.raises(AdbTransferError, match="source must not be a symbolic link"):
        _remote(FakeRunner(_result())).require_regular_file("/sdcard/file.bin", label="source")

    with pytest.raises(AdbTransferError, match="source is not a regular file"):
        _remote(FakeRunner(_false_test(), _false_test())).require_regular_file(
            "/sdcard/file.bin", label="source"
        )


def test_size_and_sha256_parse_fixed_remote_commands() -> None:
    runner = FakeRunner(_result("7 /sdcard/file.bin\n"), _result(f"{DIGEST}  /sdcard/file.bin\n"))
    remote = _remote(runner)

    assert remote.size("/sdcard/file.bin") == 7
    assert remote.sha256("/sdcard/file.bin") == DIGEST
    assert runner.commands[0][-3:] == ("wc", "-c", "/sdcard/file.bin")
    assert runner.commands[1][-1] == "/sdcard/file.bin"


def test_size_and_sha256_reject_malformed_evidence() -> None:
    with pytest.raises(AdbTransferError, match="invalid output"):
        _remote(FakeRunner(_result("garbage\n"))).size("/sdcard/file.bin")

    with pytest.raises(AdbTransferError, match="negative"):
        _remote(FakeRunner(_result("-1 file\n"))).size("/sdcard/file.bin")

    with pytest.raises(AdbTransferError, match="invalid output"):
        _remote(FakeRunner(_result("not-a-digest\n"))).sha256("/sdcard/file.bin")


def test_commit_stage_detects_no_clobber_race() -> None:
    runner = FakeRunner(_result(), _result())

    with pytest.raises(AdbTransferError, match="appeared"):
        _remote(runner).commit_stage(
            "/sdcard/.hostops.tmp",
            "/sdcard/file.bin",
            replace=False,
        )

    assert runner.commands[0][-4:] == (
        "mv",
        "-nT",
        "/sdcard/.hostops.tmp",
        "/sdcard/file.bin",
    )


def test_commit_stage_replace_requires_staging_to_disappear() -> None:
    with pytest.raises(AdbTransferError, match="left staging"):
        _remote(FakeRunner(_result(), _result())).commit_stage(
            "/sdcard/.hostops.tmp",
            "/sdcard/file.bin",
            replace=True,
        )


def test_commit_stage_succeeds_when_staging_disappears() -> None:
    runner = FakeRunner(_result(), _false_test())

    _remote(runner).commit_stage(
        "/sdcard/.hostops.tmp",
        "/sdcard/file.bin",
        replace=False,
    )


def test_cleanup_best_effort_and_strict_modes() -> None:
    assert _remote(FakeRunner(_result())).cleanup("/sdcard/.tmp") is True
    assert (
        _remote(FakeRunner(_result(exit_code=1))).cleanup("/sdcard/.tmp", best_effort=True) is False
    )
    with pytest.raises(AdbTransferError, match="staging cleanup"):
        _remote(FakeRunner(_result(stderr="denied", exit_code=1))).cleanup("/sdcard/.tmp")


def test_remote_command_truncation_and_noncompleted_state_fail_closed() -> None:
    with pytest.raises(AdbTransferError, match="truncated"):
        _remote(FakeRunner(_result("device\n", stdout_truncated=True))).require_ready()

    with pytest.raises(AdbTransferError, match="remote test"):
        _remote(
            FakeRunner(
                _result(
                    state=ProcessState.TIMED_OUT,
                    exit_code=None,
                    stderr="timeout",
                )
            )
        ).require_directory("/sdcard/tmp")


@settings(max_examples=200, deadline=None, derandomize=True, database=None)
@given(segments=st.lists(_REMOTE_SEGMENT, min_size=1, max_size=8))
def test_remote_path_property_accepts_single_root_and_rejects_double_root(
    segments: list[str],
) -> None:
    path = "/" + "/".join(segments)
    assert normalize_remote_file_path(path) == path
    with pytest.raises(AdbTransferError):
        normalize_remote_file_path("/" + path)


def test_remote_path_validation_is_literal_and_absolute() -> None:
    assert normalize_remote_file_path("/sdcard/Download/file.bin") == "/sdcard/Download/file.bin"
    for invalid in (
        "relative.bin",
        "/",
        "/sdcard/../data/file.bin",
        "/sdcard/file name.bin",
        "/sdcard//file.bin",
        "//sdcard/file.bin",
    ):
        with pytest.raises(AdbTransferError):
            normalize_remote_file_path(invalid)
