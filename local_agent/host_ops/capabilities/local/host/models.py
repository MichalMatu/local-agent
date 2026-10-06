"""Structured local host capability facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class HostProfile:
    hostname: str
    system: str
    release: str
    architecture: str
    logical_cpu_count: int | None
    memory_total_bytes: int | None
    root_total_bytes: int
    root_free_bytes: int
    gpu_devices: tuple[str, ...] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "hostname": self.hostname,
            "system": self.system,
            "release": self.release,
            "architecture": self.architecture,
            "logical_cpu_count": self.logical_cpu_count,
            "memory_total_bytes": self.memory_total_bytes,
            "gpu_devices": list(self.gpu_devices) if self.gpu_devices is not None else None,
            "root_total_bytes": self.root_total_bytes,
            "root_free_bytes": self.root_free_bytes,
        }
