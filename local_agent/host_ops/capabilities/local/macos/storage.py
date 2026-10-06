"""Bounded control of explicitly identified external macOS storage devices."""

from __future__ import annotations

import platform
import plistlib
import re

from local_agent.host_ops.core.execution import ExecutionLimits, ProcessResult, ProcessRunner

from .models import MacOSStorageActionResult

_DISKUTIL = "/usr/sbin/diskutil"
_DISK_IDENTIFIER = re.compile(r"^disk\d+(?:s\d+)?$")


class MacOSStorageControlError(RuntimeError):
    """Raised when a macOS storage action cannot be performed safely."""


class MacOSStorageController:
    """Mount, unmount or eject one explicitly identified external disk/volume."""

    def __init__(
        self,
        runner: ProcessRunner | None = None,
        *,
        system_name: str | None = None,
    ) -> None:
        self._runner = runner or ProcessRunner()
        self._system_name = system_name or platform.system()

    def mount(
        self,
        identifier: str,
        *,
        limits: ExecutionLimits | None = None,
    ) -> MacOSStorageActionResult:
        self._require_external(identifier, limits=limits)
        return self._action("mount", identifier, limits=limits)

    def unmount(
        self,
        identifier: str,
        *,
        limits: ExecutionLimits | None = None,
    ) -> MacOSStorageActionResult:
        self._require_external(identifier, limits=limits)
        return self._action("unmount", identifier, limits=limits)

    def eject(
        self,
        identifier: str,
        *,
        limits: ExecutionLimits | None = None,
    ) -> MacOSStorageActionResult:
        info = self._require_external(identifier, limits=limits)
        if info.get("Whole") is not True:
            raise MacOSStorageControlError("eject requires a whole external disk identifier")
        return self._action("eject", identifier, limits=limits)

    def _require_external(
        self,
        identifier: str,
        *,
        limits: ExecutionLimits | None,
    ) -> dict[object, object]:
        self._require_macos()
        _validate_identifier(identifier)
        result = self._runner.run((_DISKUTIL, "info", "-plist", identifier), limits=limits)
        payload = _plist(result, f"inspect storage target {identifier}")
        if not isinstance(payload, dict):
            raise MacOSStorageControlError(
                f"inspect storage target {identifier}: unexpected diskutil schema"
            )
        if payload.get("Internal") is not False:
            raise MacOSStorageControlError(
                f"storage target {identifier} is not confirmed external; refusing action"
            )
        return payload

    def _action(
        self,
        action: str,
        identifier: str,
        *,
        limits: ExecutionLimits | None,
    ) -> MacOSStorageActionResult:
        result = self._runner.run((_DISKUTIL, action, identifier), limits=limits)
        _require_ok(result, f"{action} storage target {identifier}")
        return MacOSStorageActionResult(
            action=action,
            identifier=identifier,
            message=result.stdout.strip(),
        )

    def _require_macos(self) -> None:
        if self._system_name != "Darwin":
            raise MacOSStorageControlError(
                f"macOS storage control requires Darwin, current system is {self._system_name!r}"
            )


def _validate_identifier(identifier: str) -> None:
    if not isinstance(identifier, str) or not _DISK_IDENTIFIER.fullmatch(identifier):
        raise MacOSStorageControlError("storage identifier must match diskN or diskNsN")


def _plist(result: ProcessResult, action: str) -> object:
    _require_ok(result, action)
    try:
        return plistlib.loads(result.stdout.encode("utf-8"))
    except (plistlib.InvalidFileException, ValueError) as exc:
        raise MacOSStorageControlError(f"{action}: invalid plist output") from exc


def _require_ok(result: ProcessResult, action: str) -> None:
    if result.ok and not result.stdout_truncated:
        return
    if result.stdout_truncated:
        raise MacOSStorageControlError(f"{action}: command stdout was truncated")
    detail = result.stderr.strip() or result.error or f"exit_code={result.exit_code}"
    raise MacOSStorageControlError(f"{action}: {detail}")
