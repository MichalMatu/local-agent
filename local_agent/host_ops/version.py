"""Installed package and machine-readable CLI contract versions."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

JSON_CONTRACT_VERSION = 1


def package_version() -> str:
    try:
        return version("host-ops")
    except PackageNotFoundError:
        return "0+unknown"
