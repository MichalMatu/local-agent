#!/usr/bin/env python3
"""Startup-loaded runtime timeout configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

MIN_TIMEOUT = 1


@dataclass(frozen=True)
class TimeoutConfig:
    command_default: int
    command_max: int
    idle_default: int
    idle_max: int
    task_default: int
    task_max: int


_DEFAULTS = {
    "command_default": 900,
    "command_max": 7200,
    "idle_default": 300,
    "idle_max": 3600,
    "task_default": 1800,
    "task_max": 21600,
}

_ENV_NAMES = {
    "command_default": "LOCAL_AGENT_COMMAND_TIMEOUT_DEFAULT",
    "command_max": "LOCAL_AGENT_COMMAND_TIMEOUT_MAX",
    "idle_default": "LOCAL_AGENT_IDLE_TIMEOUT_DEFAULT",
    "idle_max": "LOCAL_AGENT_IDLE_TIMEOUT_MAX",
    "task_default": "LOCAL_AGENT_TASK_TIMEOUT_DEFAULT",
    "task_max": "LOCAL_AGENT_TASK_TIMEOUT_MAX",
}


def _read_positive_int(name: str, raw: str) -> int:
    try:
        value = int(raw.strip())
    except (AttributeError, ValueError):
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if value < MIN_TIMEOUT:
        raise ValueError(f"{name} must be at least {MIN_TIMEOUT} second, got {value}")
    return value


def load_timeout_config(environ: Mapping[str, str] | None = None) -> TimeoutConfig:
    source = os.environ if environ is None else environ
    values: dict[str, int] = {}
    for field, name in _ENV_NAMES.items():
        raw = source.get(name)
        values[field] = (
            _DEFAULTS[field] if raw is None else _read_positive_int(name, raw)
        )

    for kind in ("command", "idle", "task"):
        default = values[f"{kind}_default"]
        maximum = values[f"{kind}_max"]
        if default > maximum:
            raise ValueError(
                f"{_ENV_NAMES[f'{kind}_default']} ({default}) cannot exceed "
                f"{_ENV_NAMES[f'{kind}_max']} ({maximum})"
            )
    return TimeoutConfig(**values)


TIMEOUTS = load_timeout_config()
