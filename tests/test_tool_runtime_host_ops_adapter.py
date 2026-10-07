from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_agent.host_ops.capabilities.local.adb import AdbClient
from local_agent.host_ops.capabilities.local.files import LocalArtifactInspector
from local_agent.host_ops.capabilities.remote.ssh import (
    SshClient,
    SshFileTransfer,
    SshTransferError,
    SshTransferResult,
)
from local_agent.host_ops.core.config import HostTarget
from local_agent.host_ops.core.execution import ExecutionLimits, ProcessResult, ProcessState
from local_agent.tool_runtime.contract import AuthorityCeiling, SemanticEffect
from local_agent.tool_runtime.host_ops_adapter import (
    ADB_IDENTITY_TOOL,
    ARTIFACT_INSPECT_TOOL,
    SSH_CHECK_TOOL,
    SSH_PULL_TOOL,
    SSH_PUSH_TOOL,
    adb_identity_invocation,
    adb_identity_result,
    artifact_inspect_invocation,
    artifact_inspect_result,
    ssh_check_invocation,
    ssh_check_result,
    ssh_pull_error,
    ssh_pull_invocation,
    ssh_pull_result,
    ssh_push_error,
    ssh_push_invocation,
)


_TEST_IDENTITY = "/tmp/host_ops_test_key"


def _completed(stdout: str = "") -> ProcessResult:
    return ProcessResult(
        state=ProcessState.COMPLETED,
        exit_code=0,
        stdout=stdout,
        stderr="",
        duration_seconds=0.001,
    )


class _Runner:
    def __init__(self, result: ProcessResult | None = None) -> None:
        self.result = result or _completed()
        self.commands: list[tuple[str, ...]] = []
        self.limits: list[ExecutionLimits | None] = []

    def run(self, command, *, limits=None, **_kwargs):
        self.commands.append(tuple(command))
        self.limits.append(limits)
        return self.result


def _target() -> HostTarget:
    return HostTarget(
        alias="phone",
        host="example.test",
        port=8022,
        user="u0_a520",
        identity_file=_TEST_IDENTITY,
    )


class _AdbRunner:
    def __init__(self, serial: str) -> None:
        self.serial = serial
        self.commands: list[tuple[str, ...]] = []
        self.properties = {
            "ro.product.manufacturer": "samsung",
            "ro.product.model": "SM-S906B",
            "ro.product.name": "r0sxxx",
            "ro.product.device": "r0s",
            "ro.build.version.release": "16",
            "ro.build.version.sdk": "36",
            "ro.build.fingerprint": "samsung/r0sxxx/r0s:16/test:user/release-keys",
        }

    def run(self, command, *, limits=None, **_kwargs):
        argv = tuple(command)
        self.commands.append(argv)
        if argv[-2:] == ("devices", "-l"):
            return _completed(
                "List of devices attached\\n"
                f"{self.serial} device product:r0sxxx model:SM-S906B "
                "device:r0s transport_id:1\\n"
            )
        if len(argv) >= 6 and argv[-2] == "getprop":
            return _completed(self.properties[argv[-1]] + "\\n")
        raise AssertionError(f"unexpected ADB command: {argv!r}")

class ToolRuntimeHostOpsAdapterTests(unittest.TestCase):
    def test_adb_identity_projects_real_client_without_promoting_wireless_locator(
        self,
    ) -> None:
        serial = "192.168.0.100:38871"
        limits = ExecutionLimits(timeout_seconds=7.0)
        runner = _AdbRunner(serial)
        invocation = adb_identity_invocation(
            serial,
            limits=limits,
            scheduler_resources=(),
        )
        legacy = AdbClient(
            runner,
            resolver=lambda name: "/opt/android/platform-tools/adb"
            if name == "adb"
            else None,
        ).identity(serial, limits=limits)
        projected = adb_identity_result(invocation, legacy)

        self.assertEqual(projected.payload, legacy.as_dict())
        self.assertEqual(projected.tool, ADB_IDENTITY_TOOL)
        self.assertEqual(projected.tool.effect, SemanticEffect.ACTIVE_READ)
        self.assertEqual(
            projected.tool.authority,
            AuthorityCeiling.FIXED_REMOTE_DEVICE_EXEC,
        )
        self.assertEqual(invocation.scheduler_resources, ())
        self.assertEqual(projected.target.name, serial)
        self.assertEqual(projected.target.locator.kind, "adb_serial")
        self.assertEqual(projected.target.locator.attributes, {"serial": serial})
        identity = projected.target.identity_evidence[0]
        self.assertEqual(identity.kind, "adb_identity_profile")
        self.assertEqual(identity.attributes["model"], "SM-S906B")
        self.assertEqual(
            identity.attributes["build_fingerprint"],
            "samsung/r0sxxx/r0s:16/test:user/release-keys",
        )

    def test_ssh_pull_preserves_success_payload_and_partial_effect_failure(
        self,
    ) -> None:
        limits = ExecutionLimits(timeout_seconds=9.0)
        target = _target()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.bin"
            invocation = ssh_pull_invocation(
                target,
                "/remote/result.bin",
                destination,
                replace=False,
                max_bytes=4096,
                limits=limits,
                scheduler_resources=(),
            )
            legacy = SshTransferResult(
                direction="pull",
                target="phone",
                source="/remote/result.bin",
                destination=str(destination),
                size_bytes=12,
                sha256="a" * 64,
                replaced_existing=False,
                local_directory_synced=True,
            )
            projected = ssh_pull_result(invocation, legacy)

        self.assertEqual(projected.payload, legacy.as_dict())
        self.assertEqual(projected.tool, SSH_PULL_TOOL)
        self.assertEqual(projected.tool.effect, SemanticEffect.MUTATION)
        self.assertEqual(
            projected.tool.authority,
            AuthorityCeiling.FIXED_REMOTE_DEVICE_EXEC,
        )
        self.assertEqual(invocation.scheduler_resources, ())
        self.assertEqual(projected.artifacts[0].path, legacy.destination)
        self.assertEqual(projected.artifacts[0].sha256, legacy.sha256)

        failure = SshTransferError(
            "local staging cleanup failed after SSH pull",
            action_attempted=True,
            committed=True,
            cleanup_failed=True,
        )
        failed = ssh_pull_error(invocation, failure)
        self.assertFalse(failed.ok)
        self.assertTrue(failed.partial_effect.action_attempted)
        self.assertTrue(failed.partial_effect.committed)
        self.assertTrue(failed.partial_effect.cleanup_failed)
        self.assertEqual(failed.error.code, "ssh_transfer_failed")
    def test_artifact_inspect_projects_real_production_result_without_legacy_drift(
        self,
    ) -> None:
        limits = ExecutionLimits(timeout_seconds=5.0)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "artifact.bin"
            source.write_bytes(b"artifact-data")
            invocation = artifact_inspect_invocation(
                source,
                max_bytes=1024,
                limits=limits,
                scheduler_resources=(),
            )
            legacy = LocalArtifactInspector().inspect(
                source,
                max_bytes=1024,
                limits=limits,
            )
            projected = artifact_inspect_result(invocation, legacy)

        self.assertEqual(projected.payload, legacy.as_dict())
        self.assertEqual(projected.tool, ARTIFACT_INSPECT_TOOL)
        self.assertEqual(projected.tool.effect, SemanticEffect.PASSIVE_READ)
        self.assertEqual(projected.tool.authority, AuthorityCeiling.NONE)
        self.assertEqual(invocation.scheduler_resources, ())
        self.assertEqual(projected.artifacts[0].sha256, legacy.sha256)
        self.assertEqual(
            projected.target.identity_evidence[0].attributes["real_path"],
            str(legacy.real_path),
        )

    def test_ssh_check_projects_real_client_result_and_keeps_target_out_of_resources(
        self,
    ) -> None:
        limits = ExecutionLimits(timeout_seconds=7.0)
        runner = _Runner(_completed("u0_a520\n"))
        target = _target()
        invocation = ssh_check_invocation(
            target,
            limits=limits,
            scheduler_resources=(),
        )
        legacy = SshClient(runner).check(target, limits=limits)
        projected = ssh_check_result(invocation, legacy)

        self.assertEqual(projected.payload, legacy.as_dict())
        self.assertIs(projected.process, legacy.process)
        self.assertTrue(projected.ok)
        self.assertEqual(projected.tool, SSH_CHECK_TOOL)
        self.assertEqual(projected.tool.effect, SemanticEffect.ACTIVE_READ)
        self.assertEqual(
            projected.tool.authority,
            AuthorityCeiling.FIXED_REMOTE_DEVICE_EXEC,
        )
        self.assertEqual(invocation.scheduler_resources, ())
        self.assertEqual(projected.target.name, "phone")
        self.assertEqual(
            projected.target.locator.attributes,
            {"host": "example.test", "port": 8022},
        )
        identity = projected.target.identity_evidence[0]
        self.assertEqual(identity.kind, "ssh_remote_user")
        self.assertEqual(identity.attributes["remote_user"], "u0_a520")
        self.assertTrue(identity.attributes["identity_matches"])

    def test_ssh_push_ambiguous_commit_failure_preserves_existing_partial_effect_evidence(
        self,
    ) -> None:
        limits = ExecutionLimits(timeout_seconds=5.0)
        target = _target()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "firmware.bin"
            payload = b"firmware-data"
            source.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            invocation = ssh_push_invocation(
                target,
                source,
                "/remote/firmware.bin",
                replace=False,
                max_bytes=1024,
                limits=limits,
                scheduler_resources=(),
            )
            transfer = SshFileTransfer(_Runner())
            with (
                patch.object(transfer, "_require_remote_directory"),
                patch.object(
                    transfer,
                    "_validate_remote_destination",
                    return_value=False,
                ),
                patch.object(
                    transfer,
                    "_remote_size",
                    return_value=len(payload),
                ),
                patch.object(
                    transfer,
                    "_remote_sha256",
                    return_value=digest,
                ),
                patch(
                    "local_agent.host_ops.capabilities.remote.ssh.transfer."
                    "_commit_remote_no_clobber",
                    side_effect=SshTransferError(
                        "commit timed out",
                        action_attempted=True,
                    ),
                ),
                patch(
                    "local_agent.host_ops.capabilities.remote.ssh.transfer."
                    "_cleanup_remote_stage",
                    return_value=True,
                ),
            ):
                with self.assertRaisesRegex(SshTransferError, "commit timed out") as caught:
                    transfer.push(
                        target,
                        source,
                        "/remote/firmware.bin",
                        max_bytes=1024,
                        limits=limits,
                    )

        projected = ssh_push_error(invocation, caught.exception)
        self.assertFalse(projected.ok)
        self.assertEqual(projected.tool, SSH_PUSH_TOOL)
        self.assertEqual(projected.tool.effect, SemanticEffect.MUTATION)
        self.assertEqual(
            projected.tool.authority,
            AuthorityCeiling.FIXED_REMOTE_DEVICE_EXEC,
        )
        self.assertEqual(invocation.scheduler_resources, ())
        self.assertTrue(projected.partial_effect.action_attempted)
        self.assertFalse(projected.partial_effect.committed)
        self.assertFalse(projected.partial_effect.cleanup_failed)
        self.assertEqual(projected.error.code, "ssh_transfer_failed")
        self.assertEqual(projected.error.message, "commit timed out")


if __name__ == "__main__":
    unittest.main()
