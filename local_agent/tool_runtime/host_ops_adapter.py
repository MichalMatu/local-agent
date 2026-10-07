"""Pure projections from existing Host Ops models into Tool Runtime contract v1.

These helpers do not execute tools, schedule work, derive resources or change Host Ops CLI output.
Callers must pass scheduler resources already admitted by Local Agent.
"""

from __future__ import annotations

from pathlib import Path

from local_agent.host_ops.capabilities.local.files.models import ArtifactInspectionResult
from local_agent.host_ops.capabilities.remote.ssh.checks import SshCheckResult
from local_agent.host_ops.capabilities.remote.ssh.transfer import (
    SshTransferError,
    SshTransferResult,
)
from local_agent.host_ops.core.config import HostTarget
from local_agent.host_ops.core.execution import ExecutionLimits

from .contract import (
    ArtifactEvidence,
    AuthorityCeiling,
    IdentityEvidence,
    OperationTarget,
    PartialEffectEvidence,
    SemanticEffect,
    ToolDescriptor,
    ToolError,
    ToolInvocation,
    ToolResult,
    TransportLocator,
)

ARTIFACT_INSPECT_TOOL = ToolDescriptor(
    tool_id="host_ops.artifact.inspect",
    effect=SemanticEffect.PASSIVE_READ,
    authority=AuthorityCeiling.NONE,
)
SSH_CHECK_TOOL = ToolDescriptor(
    tool_id="host_ops.ssh.check",
    effect=SemanticEffect.ACTIVE_READ,
    authority=AuthorityCeiling.FIXED_REMOTE_DEVICE_EXEC,
)
SSH_PUSH_TOOL = ToolDescriptor(
    tool_id="host_ops.ssh.push",
    effect=SemanticEffect.MUTATION,
    authority=AuthorityCeiling.FIXED_REMOTE_DEVICE_EXEC,
)


def _resources(value: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(
            "scheduler_resources must come from Local Agent admission as a tuple"
        )
    return value


def _ssh_target(target: HostTarget) -> OperationTarget:
    return OperationTarget(
        kind="ssh_host",
        name=target.alias,
        locator=TransportLocator(
            kind="ssh",
            attributes={"host": target.host, "port": target.port},
        ),
    )


def _require_tool(invocation: ToolInvocation, expected: ToolDescriptor) -> None:
    if invocation.tool != expected:
        raise ValueError(
            f"tool invocation identity mismatch: expected {expected.tool_id!r}, "
            f"got {invocation.tool.tool_id!r}"
        )


def artifact_inspect_invocation(
    source: Path,
    *,
    max_bytes: int,
    limits: ExecutionLimits,
    scheduler_resources: tuple[str, ...],
) -> ToolInvocation:
    requested = str(Path(source).expanduser())
    return ToolInvocation(
        tool=ARTIFACT_INSPECT_TOOL,
        arguments={"source": requested, "max_bytes": max_bytes},
        target=OperationTarget(
            kind="local_artifact",
            name=requested,
            locator=TransportLocator(
                kind="filesystem_path",
                attributes={"path": requested},
            ),
        ),
        scheduler_resources=_resources(scheduler_resources),
        execution_limits=limits,
    )


def artifact_inspect_result(
    invocation: ToolInvocation,
    result: ArtifactInspectionResult,
) -> ToolResult:
    _require_tool(invocation, ARTIFACT_INSPECT_TOOL)
    target = OperationTarget(
        kind="local_artifact",
        name=(
            invocation.target.name
            if invocation.target is not None
            else str(result.requested_path)
        ),
        locator=None if invocation.target is None else invocation.target.locator,
        identity_evidence=(
            IdentityEvidence(
                kind="artifact_content",
                attributes={
                    "real_path": str(result.real_path),
                    "size_bytes": result.size_bytes,
                    "sha256": result.sha256,
                    "modified_time_ns": result.modified_time_ns,
                },
            ),
        ),
    )
    return ToolResult(
        tool=ARTIFACT_INSPECT_TOOL,
        ok=True,
        target=target,
        payload=result.as_dict(),
        artifacts=(
            ArtifactEvidence(
                path=str(result.real_path),
                size_bytes=result.size_bytes,
                sha256=result.sha256,
            ),
        ),
    )


def ssh_check_invocation(
    target: HostTarget,
    *,
    limits: ExecutionLimits,
    scheduler_resources: tuple[str, ...],
) -> ToolInvocation:
    return ToolInvocation(
        tool=SSH_CHECK_TOOL,
        arguments={},
        target=_ssh_target(target),
        scheduler_resources=_resources(scheduler_resources),
        execution_limits=limits,
    )


def ssh_check_result(
    invocation: ToolInvocation,
    result: SshCheckResult,
) -> ToolResult:
    _require_tool(invocation, SSH_CHECK_TOOL)
    if invocation.target is None:
        raise ValueError("SSH check invocation requires an operation target")
    target = OperationTarget(
        kind=invocation.target.kind,
        name=invocation.target.name,
        locator=invocation.target.locator,
        identity_evidence=(
            IdentityEvidence(
                kind="ssh_remote_user",
                attributes={
                    "expected_user": result.expected_user,
                    "remote_user": result.remote_user,
                    "identity_matches": result.identity_matches,
                },
            ),
        ),
    )
    return ToolResult(
        tool=SSH_CHECK_TOOL,
        ok=result.ok,
        target=target,
        payload=result.as_dict(),
        process=result.process,
    )


def ssh_push_invocation(
    target: HostTarget,
    local_source: Path,
    remote_destination: str,
    *,
    replace: bool,
    max_bytes: int,
    limits: ExecutionLimits,
    scheduler_resources: tuple[str, ...],
) -> ToolInvocation:
    return ToolInvocation(
        tool=SSH_PUSH_TOOL,
        arguments={
            "source": str(Path(local_source).expanduser()),
            "destination": remote_destination,
            "replace": replace,
            "max_bytes": max_bytes,
        },
        target=_ssh_target(target),
        scheduler_resources=_resources(scheduler_resources),
        execution_limits=limits,
    )


def ssh_push_result(
    invocation: ToolInvocation,
    result: SshTransferResult,
) -> ToolResult:
    _require_tool(invocation, SSH_PUSH_TOOL)
    if result.direction != "push":
        raise ValueError("SSH push projection requires a push transfer result")
    return ToolResult(
        tool=SSH_PUSH_TOOL,
        ok=True,
        target=invocation.target,
        payload=result.as_dict(),
        artifacts=(
            ArtifactEvidence(
                path=result.destination,
                size_bytes=result.size_bytes,
                sha256=result.sha256,
            ),
        ),
    )


def ssh_push_error(
    invocation: ToolInvocation,
    error: SshTransferError,
) -> ToolResult:
    _require_tool(invocation, SSH_PUSH_TOOL)
    return ToolResult(
        tool=SSH_PUSH_TOOL,
        ok=False,
        target=invocation.target,
        payload={},
        partial_effect=PartialEffectEvidence(
            action_attempted=error.action_attempted,
            committed=error.committed,
            cleanup_failed=error.cleanup_failed,
        ),
        error=ToolError(
            code="ssh_transfer_failed",
            message=str(error),
        ),
    )
