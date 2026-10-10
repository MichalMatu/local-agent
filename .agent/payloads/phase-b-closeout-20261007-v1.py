from pathlib import Path
import re

ROOT = Path(".")

def read(path: str) -> str:
    return (ROOT / path).read_text()

def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text)

def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise SystemExit(f"missing replacement anchor in {path}: {old[:80]!r}")
    write(path, text.replace(old, new, 1))

def replace_between(path: str, start: str, end: str, replacement: str) -> None:
    text = read(path)
    i = text.find(start)
    if i < 0:
        raise SystemExit(f"missing start in {path}: {start!r}")
    j = text.find(end, i + len(start))
    if j < 0:
        raise SystemExit(f"missing end in {path}: {end!r}")
    write(path, text[:i] + replacement + text[j:])

replace_once(
    "local_agent/host_ops/capabilities/local/adb/remote_files.py",
    '''class AdbTransferError(RuntimeError):
    """Raised when verified ADB transfer cannot complete safely."""
''',
    '''class AdbTransferError(RuntimeError):
    """Raised when verified ADB transfer cannot complete safely."""

    def __init__(
        self,
        message: str,
        *,
        action_attempted: bool = False,
        committed: bool = False,
        cleanup_failed: bool = False,
    ) -> None:
        super().__init__(message)
        self.action_attempted = action_attempted or committed
        self.committed = committed
        self.cleanup_failed = cleanup_failed
'''
)

adb_push = '''    def push(
        self,
        serial: str,
        local_source: Path,
        remote_destination: str,
        *,
        replace: bool = False,
        max_bytes: int = DEFAULT_MAX_TRANSFER_BYTES,
        limits: ExecutionLimits | None = None,
    ) -> AdbTransferResult:
        maximum = _validate_max_bytes(max_bytes)
        budget = _TransferBudget(limits or ExecutionLimits(timeout_seconds=300.0))
        normalized_serial = _normalize_serial(serial)
        source = _inspect_local_source(local_source, maximum)
        destination = normalize_remote_file_path(remote_destination)
        remote = self._remote(normalized_serial, budget)
        remote.require_ready()
        remote.require_directory(str(PurePosixPath(destination).parent))
        replaced_existing = remote.validate_destination(destination, replace=replace)
        stage = str(PurePosixPath(destination).parent / f".hostops-adb-{secrets.token_hex(12)}.tmp")
        stage_present = False
        stage_may_exist = False
        action_attempted = False
        committed = False

        try:
            action_attempted = True
            stage_may_exist = True
            remote.push(source.path, stage)
            stage_present = True
            remote_size = remote.size(stage)
            remote_sha256 = remote.sha256(stage)
            if remote_size != source.size_bytes or remote_sha256 != source.sha256:
                raise AdbTransferError("uploaded staging file failed size or SHA-256 verification")
            if _sha256_file(source.path) != source.sha256:
                raise AdbTransferError("local source changed while ADB push was in progress")

            remote.commit_stage(stage, destination, replace=replace)
            committed = True
            stage_present = False
            remote.require_regular_file(destination, label="destination")
            if remote.size(destination) != source.size_bytes:
                raise AdbTransferError("remote destination failed post-commit size verification")
            if remote.sha256(destination) != source.sha256:
                raise AdbTransferError("remote destination failed post-commit SHA-256 verification")
            return AdbTransferResult(
                direction="push",
                serial=normalized_serial,
                source=str(source.path),
                destination=destination,
                size_bytes=source.size_bytes,
                sha256=source.sha256,
                replaced_existing=replaced_existing,
            )
        except (AdbTransferError, OSError, ValueError) as exc:
            cleanup_failed = False
            if stage_present or (stage_may_exist and not committed):
                try:
                    cleanup_failed = not remote.cleanup(stage, best_effort=True)
                except (AdbTransferError, OSError, ValueError):
                    cleanup_failed = True
            raise _adb_transfer_error(
                exc,
                action_attempted=action_attempted,
                committed=committed,
                cleanup_failed=cleanup_failed,
            ) from exc

'''

adb_pull = '''    def pull(
        self,
        serial: str,
        remote_source: str,
        local_destination: Path,
        *,
        replace: bool = False,
        max_bytes: int = DEFAULT_MAX_TRANSFER_BYTES,
        limits: ExecutionLimits | None = None,
    ) -> AdbTransferResult:
        maximum = _validate_max_bytes(max_bytes)
        budget = _TransferBudget(limits or ExecutionLimits(timeout_seconds=300.0))
        normalized_serial = _normalize_serial(serial)
        source = normalize_remote_file_path(remote_source)
        remote = self._remote(normalized_serial, budget)
        remote.require_ready()
        remote.require_regular_file(source, label="source")
        remote_size = remote.size(source)
        if remote_size > maximum:
            raise AdbTransferError(f"remote source exceeds max_bytes ({remote_size} > {maximum})")
        remote_sha256 = remote.sha256(source)
        destination, replaced_existing = _prepare_local_destination(
            local_destination,
            replace=replace,
        )
        stage = destination.parent / f".hostops-adb-{secrets.token_hex(12)}.tmp"
        action_attempted = False
        committed = False
        failure: AdbTransferError | OSError | ValueError | None = None
        result: AdbTransferResult | None = None

        try:
            action_attempted = True
            remote.pull(source, stage)
            staged = _inspect_local_source(stage, maximum)
            if staged.size_bytes != remote_size or staged.sha256 != remote_sha256:
                raise AdbTransferError(
                    "downloaded staging file failed size or SHA-256 verification"
                )
            if remote.size(source) != remote_size or remote.sha256(source) != remote_sha256:
                raise AdbTransferError("remote source changed while ADB pull was in progress")
            _fsync_file(stage)
            _commit_local_stage(stage, destination, replace=replace)
            committed = True
            directory_synced = _sync_directory(destination.parent)
            result = AdbTransferResult(
                direction="pull",
                serial=normalized_serial,
                source=source,
                destination=str(destination),
                size_bytes=remote_size,
                sha256=remote_sha256,
                replaced_existing=replaced_existing,
                local_directory_synced=directory_synced,
            )
        except (AdbTransferError, OSError, ValueError) as exc:
            failure = exc

        cleanup_failed = False
        if stage.exists() or stage.is_symlink():
            try:
                stage.unlink(missing_ok=True)
            except OSError:
                cleanup_failed = True

        if failure is not None:
            raise _adb_transfer_error(
                failure,
                action_attempted=action_attempted,
                committed=committed,
                cleanup_failed=cleanup_failed,
            ) from failure
        if cleanup_failed:
            raise AdbTransferError(
                "local staging cleanup failed after ADB pull",
                action_attempted=action_attempted,
                committed=committed,
                cleanup_failed=True,
            )
        assert result is not None
        return result

'''

replace_between("local_agent/host_ops/capabilities/local/adb/transfer.py", "    def push(\n", "    def pull(\n", adb_push)
replace_between("local_agent/host_ops/capabilities/local/adb/transfer.py", "    def pull(\n", "    def _remote(\n", adb_pull)

replace_once(
    "local_agent/host_ops/capabilities/local/adb/transfer.py",
    "@dataclass(frozen=True, slots=True)\nclass _LocalSource:\n",
    '''def _adb_transfer_error(
    exc: AdbTransferError | OSError | ValueError,
    *,
    action_attempted: bool,
    committed: bool,
    cleanup_failed: bool,
) -> AdbTransferError:
    if isinstance(exc, AdbTransferError):
        action_attempted = action_attempted or exc.action_attempted
        committed = committed or exc.committed
        cleanup_failed = cleanup_failed or exc.cleanup_failed
    return AdbTransferError(
        str(exc),
        action_attempted=action_attempted or committed,
        committed=committed,
        cleanup_failed=cleanup_failed,
    )


@dataclass(frozen=True, slots=True)
class _LocalSource:
'''
)

replace_once(
    "local_agent/host_ops/capabilities/local/adb/transfer.py",
    '''def _commit_local_stage(stage: Path, destination: Path, *, replace: bool) -> None:
    if replace:
        os.replace(stage, destination)
        return
    try:
        os.link(stage, destination)
    except FileExistsError as exc:
        raise AdbTransferError("local destination appeared during no-clobber commit") from exc
    except OSError as exc:
        raise AdbTransferError(f"local no-clobber commit failed: {exc}") from exc
    stage.unlink()
''',
    '''def _commit_local_stage(stage: Path, destination: Path, *, replace: bool) -> None:
    if replace:
        os.replace(stage, destination)
        return
    try:
        os.link(stage, destination)
    except FileExistsError as exc:
        raise AdbTransferError("local destination appeared during no-clobber commit") from exc
    except OSError as exc:
        raise AdbTransferError(f"local no-clobber commit failed: {exc}") from exc
    try:
        stage.unlink()
    except OSError as exc:
        raise AdbTransferError(
            f"local staging cleanup failed after no-clobber commit: {exc}",
            action_attempted=True,
            committed=True,
            cleanup_failed=True,
        ) from exc
'''
)

for _ in range(2):
    replace_once(
        "local_agent/host_ops/cli/commands/adb.py",
        "    except (AdbTransferError, ValueError) as exc:\n        return _transfer_error(str(exc), as_json=as_json)\n",
        "    except (AdbTransferError, ValueError) as exc:\n        return _transfer_error(exc, as_json=as_json)\n",
    )

replace_once(
    "local_agent/host_ops/cli/commands/adb.py",
    '''def _transfer_error(message: str, *, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"error": message}, sort_keys=True), file=sys.stderr)
    else:
        print(f"ADB transfer failed: {message}", file=sys.stderr)
    return 1
''',
    '''def _transfer_error(error: AdbTransferError | ValueError, *, as_json: bool) -> int:
    message = str(error)
    if as_json:
        payload: dict[str, object] = {"error": message}
        if isinstance(error, AdbTransferError):
            payload.update(
                action_attempted=error.action_attempted,
                committed=error.committed,
                cleanup_failed=error.cleanup_failed,
            )
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
    else:
        print(f"ADB transfer failed: {message}", file=sys.stderr)
    return 1
'''
)

replace_once(
    "local_agent/host_ops/capabilities/remote/ssh/transfer.py",
    '''class SshTransferError(RuntimeError):
    """Raised when a verified SSH file transfer cannot be completed safely."""
''',
    '''class SshTransferError(RuntimeError):
    """Raised when a verified SSH file transfer cannot be completed safely."""

    def __init__(
        self,
        message: str,
        *,
        action_attempted: bool = False,
        committed: bool = False,
        cleanup_failed: bool = False,
    ) -> None:
        super().__init__(message)
        self.action_attempted = action_attempted or committed
        self.committed = committed
        self.cleanup_failed = cleanup_failed
'''
)

ssh_push = '''    def push(
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
        stage_may_exist = False
        action_attempted = False
        committed = False

        try:
            action_attempted = True
            stage_may_exist = True
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
            committed = True

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
            cleanup_failed = False
            if stage_present or (stage_may_exist and not committed):
                try:
                    cleanup_failed = not self._cleanup_remote_stage(
                        target,
                        stage,
                        budget,
                        best_effort=True,
                    )
                except (OSError, SshTransferError, ValueError):
                    cleanup_failed = True
            raise _ssh_transfer_error(
                exc,
                action_attempted=action_attempted,
                committed=committed,
                cleanup_failed=cleanup_failed,
            ) from exc

'''

ssh_pull = '''    def pull(
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
        action_attempted = False
        committed = False
        failure: OSError | SshTransferError | ValueError | None = None
        result: SshTransferResult | None = None

        try:
            action_attempted = True
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
                committed = True
            else:
                try:
                    os.link(stage, destination)
                except FileExistsError as exc:
                    raise SshTransferError(
                        "local destination appeared during no-clobber commit"
                    ) from exc
                except OSError as exc:
                    raise SshTransferError(f"local no-clobber commit failed: {exc}") from exc
                committed = True
                try:
                    stage.unlink()
                except OSError as exc:
                    raise SshTransferError(
                        f"local staging cleanup failed after no-clobber commit: {exc}",
                        action_attempted=True,
                        committed=True,
                        cleanup_failed=True,
                    ) from exc
            directory_synced = _sync_directory(destination.parent)
            result = SshTransferResult(
                direction="pull",
                target=target.alias,
                source=source,
                destination=str(destination),
                size_bytes=remote_size,
                sha256=remote_sha256,
                replaced_existing=replaced_existing,
                local_directory_synced=directory_synced,
            )
        except (OSError, SshTransferError, ValueError) as exc:
            failure = exc

        cleanup_failed = False
        if stage.exists() or stage.is_symlink():
            try:
                stage.unlink(missing_ok=True)
            except OSError:
                cleanup_failed = True

        if failure is not None:
            raise _ssh_transfer_error(
                failure,
                action_attempted=action_attempted,
                committed=committed,
                cleanup_failed=cleanup_failed,
            ) from failure
        if cleanup_failed:
            raise SshTransferError(
                "local staging cleanup failed after SSH pull",
                action_attempted=action_attempted,
                committed=committed,
                cleanup_failed=True,
            )
        assert result is not None
        return result

'''

replace_between("local_agent/host_ops/capabilities/remote/ssh/transfer.py", "    def push(\n", "    def pull(\n", ssh_push)
replace_between("local_agent/host_ops/capabilities/remote/ssh/transfer.py", "    def pull(\n", "    def _require_remote_directory(\n", ssh_pull)

replace_once(
    "local_agent/host_ops/capabilities/remote/ssh/transfer.py",
    "@dataclass(frozen=True, slots=True)\nclass _LocalSource:\n",
    '''def _ssh_transfer_error(
    exc: OSError | SshTransferError | ValueError,
    *,
    action_attempted: bool,
    committed: bool,
    cleanup_failed: bool,
) -> SshTransferError:
    if isinstance(exc, SshTransferError):
        action_attempted = action_attempted or exc.action_attempted
        committed = committed or exc.committed
        cleanup_failed = cleanup_failed or exc.cleanup_failed
    return SshTransferError(
        str(exc),
        action_attempted=action_attempted or committed,
        committed=committed,
        cleanup_failed=cleanup_failed,
    )


@dataclass(frozen=True, slots=True)
class _LocalSource:
'''
)

ssh_path = "local_agent/host_ops/capabilities/remote/ssh/transfer.py"
ssh_text = read(ssh_path)
ssh_text = ssh_text.replace(
    'raise SshTransferError(\n            _process_failure("remote no-clobber hard-link commit", link_result)\n        )',
    'raise SshTransferError(\n            _process_failure("remote no-clobber hard-link commit", link_result),\n            action_attempted=True,\n        )',
    1,
)
ssh_text = ssh_text.replace(
    'raise SshTransferError(\n            _process_failure("remote no-clobber rename fallback", move_result)\n        )',
    'raise SshTransferError(\n            _process_failure("remote no-clobber rename fallback", move_result),\n            action_attempted=True,\n        )',
    1,
)
ssh_text = ssh_text.replace(
    'raise SshTransferError("remote destination appeared during no-clobber commit")',
    'raise SshTransferError(\n            "remote destination appeared during no-clobber commit",\n            action_attempted=True,\n        )',
    1,
)
ssh_text = ssh_text.replace(
    'raise SshTransferError(\n            _process_failure("remote no-clobber rename fallback", move_result)\n        )',
    'raise SshTransferError(\n            _process_failure("remote no-clobber rename fallback", move_result),\n            action_attempted=True,\n        )',
    1,
)
ssh_text = ssh_text.replace(
    'raise SshTransferError(\n        "remote no-clobber rename fallback left the staging file in place"\n    )',
    'raise SshTransferError(\n        "remote no-clobber rename fallback left the staging file in place",\n        action_attempted=True,\n    )',
    1,
)
write(ssh_path, ssh_text)

for _ in range(2):
    replace_once(
        "local_agent/host_ops/cli/commands/ssh.py",
        "    except SshTransferError as exc:\n        _emit_transfer_error(str(exc), as_json=as_json)\n        return 1\n",
        "    except SshTransferError as exc:\n        _emit_transfer_error(exc, as_json=as_json)\n        return 1\n",
    )

replace_once(
    "local_agent/host_ops/cli/commands/ssh.py",
    '''def _emit_transfer_error(message: str, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"ok": False, "error": message}, sort_keys=True), file=sys.stderr)
    else:
        print(f"SSH transfer failed: {message}", file=sys.stderr)
''',
    '''def _emit_transfer_error(error: SshTransferError, *, as_json: bool) -> None:
    message = str(error)
    if as_json:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": message,
                    "action_attempted": error.action_attempted,
                    "committed": error.committed,
                    "cleanup_failed": error.cleanup_failed,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
    else:
        print(f"SSH transfer failed: {message}", file=sys.stderr)
'''
)

# ADB regression coverage.
replace_once("host_ops_tests/unit/local_adb/test_adb_transfer_edges.py", "        self.pull_payload = PAYLOAD\n", "        self.pull_payload = PAYLOAD\n        self.push_error: AdbTransferError | None = None\n        self.commit_error: AdbTransferError | None = None\n        self.cleanup_ok = True\n")
replace_once("host_ops_tests/unit/local_adb/test_adb_transfer_edges.py", '''    def push(self, source: Path, destination: str) -> None:
        self.calls.append(("push", source, destination))
''', '''    def push(self, source: Path, destination: str) -> None:
        self.calls.append(("push", source, destination))
        if self.push_error is not None:
            raise self.push_error
''')
replace_once("host_ops_tests/unit/local_adb/test_adb_transfer_edges.py", '''    def commit_stage(self, stage: str, destination: str, *, replace: bool) -> None:
        self.calls.append(("commit", stage, destination, replace))
''', '''    def commit_stage(self, stage: str, destination: str, *, replace: bool) -> None:
        self.calls.append(("commit", stage, destination, replace))
        if self.commit_error is not None:
            raise self.commit_error
''')
replace_once("host_ops_tests/unit/local_adb/test_adb_transfer_edges.py", '''    def cleanup(self, stage: str, *, best_effort: bool = False) -> bool:
        self.calls.append(("cleanup", stage, best_effort))
        return True
''', '''    def cleanup(self, stage: str, *, best_effort: bool = False) -> bool:
        self.calls.append(("cleanup", stage, best_effort))
        return self.cleanup_ok
''')
replace_once("host_ops_tests/unit/local_adb/test_adb_transfer_edges.py", '''    with pytest.raises(AdbTransferError, match="post-commit size"):
        _client(monkeypatch, remote).push("ABC", source, "/sdcard/input.bin")
''', '''    with pytest.raises(AdbTransferError, match="post-commit size") as exc_info:
        _client(monkeypatch, remote).push("ABC", source, "/sdcard/input.bin")

    assert exc_info.value.action_attempted is True
    assert exc_info.value.committed is True
    assert exc_info.value.cleanup_failed is False
''')
replace_once("host_ops_tests/unit/local_adb/test_adb_transfer_edges.py", "def test_pull_rejects_remote_source_larger_than_limit(\n", '''def test_push_commit_failure_reports_attempted_unknown_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(PAYLOAD)
    remote = FakeRemote()
    remote.commit_error = AdbTransferError("commit timed out", action_attempted=True)
    remote.cleanup_ok = False

    with pytest.raises(AdbTransferError, match="commit timed out") as exc_info:
        _client(monkeypatch, remote).push("ABC", source, "/sdcard/input.bin")

    assert exc_info.value.action_attempted is True
    assert exc_info.value.committed is False
    assert exc_info.value.cleanup_failed is True
    assert any(call[0] == "cleanup" for call in remote.calls)


def test_pull_sync_failure_reports_committed_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "out.bin"
    remote = FakeRemote()

    def fail_sync(_path: Path) -> bool:
        raise OSError(errno.EIO, "sync failed")

    monkeypatch.setattr(transfer_module, "_sync_directory", fail_sync)
    with pytest.raises(AdbTransferError, match="sync failed") as exc_info:
        _client(monkeypatch, remote).pull("ABC", "/sdcard/out.bin", destination)

    assert destination.read_bytes() == PAYLOAD
    assert exc_info.value.action_attempted is True
    assert exc_info.value.committed is True


def test_pull_rejects_remote_source_larger_than_limit(
''')

replace_once("host_ops_tests/unit/cli/test_adb_extended_commands.py", '''        def pull(self, *args, **kwargs):
            raise AdbTransferError("remote source is not a regular file")
''', '''        def pull(self, *args, **kwargs):
            raise AdbTransferError(
                "remote source is not a regular file",
                action_attempted=True,
                committed=True,
                cleanup_failed=False,
            )
''')
replace_once("host_ops_tests/unit/cli/test_adb_extended_commands.py", '    assert "not a regular file" in json.loads(capsys.readouterr().err)["error"]\n', '''    payload = json.loads(capsys.readouterr().err)
    assert "not a regular file" in payload["error"]
    assert payload["action_attempted"] is True
    assert payload["committed"] is True
    assert payload["cleanup_failed"] is False
''')

# SSH regression coverage.
replace_once("host_ops_tests/unit/ssh/test_transfer.py", "        destination_appears_on_link: bytes | None = None,\n    ) -> None:\n", "        destination_appears_on_link: bytes | None = None,\n        rm_error: bool = False,\n    ) -> None:\n")
replace_once("host_ops_tests/unit/ssh/test_transfer.py", "        self.destination_appears_on_link = destination_appears_on_link\n", "        self.destination_appears_on_link = destination_appears_on_link\n        self.rm_error = rm_error\n")
replace_once("host_ops_tests/unit/ssh/test_transfer.py", '''        if program == "rm":
            self.remote_files.pop(remote[-1], None)
            return _result()
''', '''        if program == "rm":
            if self.rm_error:
                return _result(exit_code=1, stderr="cleanup failed")
            self.remote_files.pop(remote[-1], None)
            return _result()
''')
replace_once("host_ops_tests/unit/ssh/test_transfer.py", "def test_push_rejects_source_over_max_bytes(tmp_path: Path) -> None:\n", '''def test_push_post_commit_verification_failure_reports_committed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"firmware-data")
    runner = FakeTransferRunner()
    transfer = SshFileTransfer(runner)
    original_size = transfer._remote_size

    def mismatched_final_size(target, path, budget):
        size = original_size(target, path, budget)
        return size + 1 if path == "/remote/firmware.bin" else size

    monkeypatch.setattr(transfer, "_remote_size", mismatched_final_size)
    with pytest.raises(SshTransferError, match="post-commit verification") as exc_info:
        transfer.push(_target(), source, "/remote/firmware.bin")

    assert exc_info.value.action_attempted is True
    assert exc_info.value.committed is True
    assert exc_info.value.cleanup_failed is False


def test_push_cleanup_failure_after_hardlink_commit_preserves_effects(
    tmp_path: Path,
) -> None:
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"firmware-data")
    runner = FakeTransferRunner(rm_error=True)

    with pytest.raises(SshTransferError, match="staging cleanup") as exc_info:
        SshFileTransfer(runner).push(_target(), source, "/remote/firmware.bin")

    assert runner.remote_files["/remote/firmware.bin"] == b"firmware-data"
    assert exc_info.value.action_attempted is True
    assert exc_info.value.committed is True
    assert exc_info.value.cleanup_failed is True


def test_push_ambiguous_commit_failure_does_not_claim_committed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "firmware.bin"
    source.write_bytes(b"firmware-data")
    runner = FakeTransferRunner()
    transfer = SshFileTransfer(runner)

    def fail_commit(*_args, **_kwargs):
        raise SshTransferError("commit timed out", action_attempted=True)

    monkeypatch.setattr(
        "local_agent.host_ops.capabilities.remote.ssh.transfer._commit_remote_no_clobber",
        fail_commit,
    )
    with pytest.raises(SshTransferError, match="commit timed out") as exc_info:
        transfer.push(_target(), source, "/remote/firmware.bin")

    assert exc_info.value.action_attempted is True
    assert exc_info.value.committed is False


def test_push_rejects_source_over_max_bytes(tmp_path: Path) -> None:
''')
replace_once("host_ops_tests/unit/ssh/test_transfer.py", "def test_pull_rejects_remote_file_over_max_bytes(tmp_path: Path) -> None:\n", '''def test_pull_sync_failure_reports_committed_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"remote-result"
    runner = FakeTransferRunner({"/remote/result.bin": payload})
    destination = tmp_path / "result.bin"

    def fail_sync(_path: Path) -> bool:
        raise OSError("sync failed")

    monkeypatch.setattr(
        "local_agent.host_ops.capabilities.remote.ssh.transfer._sync_directory",
        fail_sync,
    )
    with pytest.raises(SshTransferError, match="sync failed") as exc_info:
        SshFileTransfer(runner).pull(_target(), "/remote/result.bin", destination)

    assert destination.read_bytes() == payload
    assert exc_info.value.action_attempted is True
    assert exc_info.value.committed is True


def test_pull_rejects_remote_file_over_max_bytes(tmp_path: Path) -> None:
''')

replace_once("host_ops_tests/unit/cli/test_ssh_transfer_commands.py", '''        def push(self, *args, **kwargs):
            raise SshTransferError("digest mismatch")
''', '''        def push(self, *args, **kwargs):
            raise SshTransferError(
                "digest mismatch",
                action_attempted=True,
                committed=True,
                cleanup_failed=True,
            )
''')
replace_once("host_ops_tests/unit/cli/test_ssh_transfer_commands.py", '''    assert code == 1
    assert "digest mismatch" in json.loads(capsys.readouterr().err)["error"]
''', '''    assert code == 1
    payload = json.loads(capsys.readouterr().err)
    assert "digest mismatch" in payload["error"]
    assert payload["ok"] is False
    assert payload["action_attempted"] is True
    assert payload["committed"] is True
    assert payload["cleanup_failed"] is True
''')

# Remote-Git JSON v2 matrix tests.
replace_once("host_ops_tests/unit/cli/test_remote_git_commands.py", "def test_run_workspace_reports_target_error(monkeypatch, capsys) -> None:\n", '''def test_run_workspace_json_success_contract_and_key_set(monkeypatch, capsys) -> None:
    result = _result(prepared=True)

    class FakeRunner:
        def prepare(self, target, workspace, *, limits=None):
            return result

    monkeypatch.setattr(remote_git, "load_host_target", lambda alias: object())
    monkeypatch.setattr(remote_git, "RemoteGitRunner", FakeRunner)
    rc = remote_git._run_workspace(
        "phone",
        _workspace(),
        timeout_seconds=20.0,
        as_json=True,
        remote_argv=None,
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["prepared"] is True
    assert set(payload) == {
        "target",
        "ok",
        "prepared",
        "repository_url",
        "revision",
        "workspace",
        "lock",
        "clean_mode",
        "process",
    }


def test_run_workspace_json_process_failure_keeps_readiness_truth(monkeypatch, capsys) -> None:
    result = _result(exit_code=7, prepared=True)

    class FakeRunner:
        def run(self, target, workspace, remote_argv, *, limits=None):
            return result

    monkeypatch.setattr(remote_git, "load_host_target", lambda alias: object())
    monkeypatch.setattr(remote_git, "RemoteGitRunner", FakeRunner)
    rc = remote_git._run_workspace(
        "phone",
        _workspace(),
        timeout_seconds=20.0,
        as_json=True,
        remote_argv=("false",),
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 7
    assert payload["ok"] is False
    assert payload["prepared"] is True
    assert payload["process"]["exit_code"] == 7


def test_run_workspace_json_current_adds_only_local_repository(monkeypatch, capsys) -> None:
    result = _result(prepared=True)

    class FakeRunner:
        def prepare(self, target, workspace, *, limits=None):
            return result

    monkeypatch.setattr(remote_git, "load_host_target", lambda alias: object())
    monkeypatch.setattr(remote_git, "RemoteGitRunner", FakeRunner)
    rc = remote_git._run_workspace(
        "phone",
        _workspace(),
        timeout_seconds=20.0,
        as_json=True,
        remote_argv=None,
        local_context=_context(),
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert set(payload) == {
        "target",
        "ok",
        "prepared",
        "repository_url",
        "revision",
        "workspace",
        "lock",
        "clean_mode",
        "process",
        "local_repository",
    }


def test_run_workspace_reports_target_error(monkeypatch, capsys) -> None:
''')

# Documentation: replace whole sections to remove stale Phase B queue.
replace_between(
    "docs/host_ops/operations/JSON_CONTRACT.md",
    "## Versioning policy\n",
    "",
    ""
) if False else None
json_doc = read("docs/host_ops/operations/JSON_CONTRACT.md")
marker = "## Versioning policy\n"
matrix = '''## Frozen command-family matrix

Version 2 intentionally preserves command-specific top-level shapes. Callers consume the family
they invoked rather than assume one common envelope.

| Case | Machine-readable behavior | Exit |
| --- | --- | ---: |
| normal command success | command-specific object or array on stdout | 0 |
| ADB/macOS/artifact/browser runtime failure | error object on stderr | 1 |
| ADB verified transfer failure | error plus action_attempted, committed and cleanup_failed on stderr | 1 |
| SSH/remote-Git input validation | ok=false error object on stdout | 2 |
| SSH verified transfer failure | ok=false error plus action_attempted, committed and cleanup_failed on stderr | 1 |
| removable-media partial failure | stage/effect object on stderr with artifact_committed and storage_action_attempted | 1 |
| network probe failure | normal network result object with ok=false on stdout | 1 |
| SSH exec / remote-Git process result | process-bearing object on stdout | mapped process exit; remote-Git missing readiness is 1 |
| bounded serial deadline | normal serial result with deadline_reached=true on stdout | 0 |
| argparse rejection before command dispatch | argparse text on stderr; no JSON envelope is promised | 2 |

Transfer effect fields are conservative. action_attempted means a mutating transfer or commit
started. committed is true only after the destination is known to have crossed its commit point.
cleanup_failed means cleanup of unique staging could not be confirmed. An ambiguous timeout during
rename, move or link must not be promoted to committed=true without positive evidence.

Parser-level argparse failures remain outside the command JSON boundary in version 2. Making them
JSON-aware, changing stdout/stderr ownership, or introducing a common envelope requires a future
versioned migration.

'''
if marker not in json_doc:
    raise SystemExit("JSON contract versioning marker missing")
write("docs/host_ops/operations/JSON_CONTRACT.md", json_doc.replace(marker, matrix + marker, 1))

# Historical version wording without rewriting historical facts.
for path in ["docs/HOST_OPS_ABSORPTION_PLAN.md", "docs/CHECKPOINT_2026-10-07_HOST_OPS_RETIREMENT_HANDOFF.md"]:
    text = read(path)
    text = text.replace("preserves JSON contract version 1", "preserved JSON contract version 1 during absorption; the maintained runtime now uses contract version 2")
    text = text.replace("absorbed Host Ops JSON contract remains version ", "absorbed Host Ops JSON contract was version ")
    write(path, text)

replace_between(
    "docs/host_ops/operations/REMOVABLE_MEDIA.md",
    "## Contract\n",
    "## Non-goals\n",
    '''## Contract

The workflow inventories the exact external volume, validates external/read-write state, mounts only
when needed, re-inspects after mount, deploys through LocalArtifactDeployer, and optionally ejects
the containing whole disk only after verified deployment.

One monotonic workflow deadline spans inspect, optional mount, re-inspection, artifact deployment
and optional eject. Every stage receives only the remaining budget.

There is no automatic eject after deployment failure. Structured failures preserve stage,
mounted_by_workflow, artifact_committed and storage_action_attempted evidence. A timeout after a
side effect therefore cannot be rendered as a false clean failure.

'''
)

replace_between(
    "docs/CURRENT_HANDOFF.md",
    "## Immediate non-physical queue\n",
    "## Preferred use of Conversation Fabric\n",
    '''## Phase B closeout status

The non-physical semantic hardening queue is complete:

1. removable-media composition has one shared whole-operation deadline;
2. every maintained operation has a canonical effect/authority classification;
3. target identity, transport locator, tool-runtime lock and scheduler-resource identity are separate;
4. JSON contract version 2 fixes Remote-Git ok/readiness truth and freezes the command-family matrix;
5. ADB and SSH transfer failures preserve action-attempted, committed and cleanup evidence.

Before Phase B is frozen, require exact-head full six-job CI and normal authenticated-Chrome
acceptance for the GitHub-controlled parent self-heal. Only unavailable printer/removable-media
physical proofs may remain deferred. P2 naming/deduplication cleanup is not a blocker unless it
reveals a correctness defect.

'''
)

replace_between(
    "docs/CHECKPOINT_2026-10-07_HOST_OPS_TOOLING_PHASE_B_HANDOFF.md",
    "## Exact remaining Phase B work\n",
    "## Physical-only deferred proof\n",
    '''## Phase B closeout

Non-physical contract hardening is complete: shared removable-media deadline, canonical
effect/authority taxonomy, target/resource identity rules, JSON contract version 2 and structured
ADB/SSH partial-effect evidence.

Remaining non-physical freeze gates are evidence only:
- exact-head full six-job CI must be green;
- the GitHub-controlled parent self-heal must pass normal authenticated-Chrome acceptance after the
  verified code is loaded.

P2 cleanup remains optional after freeze unless fresh correctness evidence requires it.

'''
)
replace_between(
    "docs/CHECKPOINT_2026-10-07_HOST_OPS_TOOLING_PHASE_B_HANDOFF.md",
    "## Recommended first swarm in a fresh parent\n",
    "## Runtime / execution invariants\n",
    '''## Conversation Fabric audit status

The deadline, effect, identity and JSON-contract audits were completed in bounded reasoning-only
campaigns and have been incorporated into the maintained code and documentation. Do not replay the
completed swarm unless fresh evidence creates a new independent question.

'''
)

replace_once(
    "docs/DEVELOPMENT_PLAN.md",
    '''Current non-physical closeout order:

1. one shared whole-operation deadline for the composed removable-media workflow;
2. one effect/risk taxonomy across all maintained operations;
3. canonical target/resource identity rules for serial, ADB, disks, SSH and remote-Git scopes;
4. JSON success/error contract audit and normalization;
5. small duplication/naming cleanup revealed by those contract audits.

Physical printer and removable-media acceptance may remain deferred until hardware is actually connected/available. Do not substitute guessed device identity for live discovery.
''',
    '''Non-physical Phase B semantics are complete: shared removable-media deadline, canonical
effect/authority taxonomy, target/resource identity rules, JSON contract version 2 with the frozen
command-family matrix, and structured ADB/SSH partial-effect evidence.

Before Phase C, require exact-head full CI and normal authenticated-Chrome acceptance for the
production Bridge self-heal. Physical printer and removable-media acceptance may remain deferred
until hardware is available. P2 naming/deduplication cleanup is not a Phase B blocker unless fresh
correctness evidence requires it.
'''
)

replace_between(
    "docs/host_ops/TOOL_INVENTORY.md",
    "### P1 — normalize execution semantics\n",
    "### P1 — physical / integration proof\n",
    '''### P1 — normalize execution semantics

Complete:
1. MacOSRemovableMediaDeployer uses one shared whole-operation deadline.
2. The canonical effect/authority matrix covers every maintained operation.
3. TARGET_MODEL.md records target/resource identity rules for serial, ADB, storage, SSH and remote-Git.
4. JSON contract version 2 documents and regression-tests the command-family success/failure matrix.
5. ADB/SSH verified transfers preserve action_attempted, committed and cleanup_failed on failure.

No further non-physical semantic normalization is required before the Tool Runtime contract. P2
cleanup remains optional unless it exposes a correctness defect.

'''
)
text = read("docs/host_ops/TOOL_INVENTORY.md")
text = text.replace(
    "live normal-Chrome acceptance only when production Chat Bridge lifecycle/recovery code changes.",
    "live normal-Chrome acceptance is required for the current GitHub-controlled parent self-heal because production Chat Bridge lifecycle/recovery code changed.",
)
text = text.replace(
    "Remaining hardening:\n- effect classification is fixed by the canonical matrix above; target/resource identity normalization remains a separate Phase B item.",
    "Hardening status:\n- effect classification and target/resource identity rules are fixed for the Phase B contract.",
)
write("docs/host_ops/TOOL_INVENTORY.md", text)

for path in [
    "local_agent/host_ops/capabilities/local/adb/remote_files.py",
    "local_agent/host_ops/capabilities/local/adb/transfer.py",
    "local_agent/host_ops/cli/commands/adb.py",
    "local_agent/host_ops/capabilities/remote/ssh/transfer.py",
    "local_agent/host_ops/cli/commands/ssh.py",
    "host_ops_tests/unit/local_adb/test_adb_transfer_edges.py",
    "host_ops_tests/unit/ssh/test_transfer.py",
    "host_ops_tests/unit/cli/test_adb_extended_commands.py",
    "host_ops_tests/unit/cli/test_ssh_transfer_commands.py",
    "host_ops_tests/unit/cli/test_remote_git_commands.py",
]:
    compile(read(path), path, "exec")
