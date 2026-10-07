from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_agent.host_ops.capabilities.local.files import LocalArtifactInspector
from local_agent.host_ops.capabilities.remote.ssh import SshClient, SshFileTransfer, SshTransferError
from local_agent.host_ops.core.config import HostTarget
from local_agent.host_ops.core.execution import ExecutionLimits, ProcessResult, ProcessState
from local_agent.tool_runtime.contract import AuthorityCeiling, SemanticEffect
from local_agent.tool_runtime.host_ops_adapter import (
    ARTIFACT_INSPECT_TOOL,
    SSH_CHECK_TOOL,
    SSH_PUSH_TOOL,
    artifact_inspect_invocation,
    artifact_inspect_result,
    ssh_check_invocation,
    ssh_check_result,
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


class ToolRuntimeHostOpsAdapterTests(unittest.TestCase):
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
