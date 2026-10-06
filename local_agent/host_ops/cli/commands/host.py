"""CLI rendering for generic local host profile facts."""

from __future__ import annotations

import json
import sys

from local_agent.host_ops.capabilities.local.host import HostProfileError, HostProfiler
from local_agent.host_ops.core.execution import ExecutionLimits


def run_profile(*, timeout_seconds: float, as_json: bool) -> int:
    try:
        profile = HostProfiler().inspect(
            limits=ExecutionLimits(
                timeout_seconds=timeout_seconds,
                max_stdout_bytes=8192,
                max_stderr_bytes=8192,
            )
        )
    except (HostProfileError, ValueError) as exc:
        if as_json:
            print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        else:
            print(f"host profile failed: {exc}", file=sys.stderr)
        return 1

    payload = profile.as_dict()
    if as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(" ".join(f"{key}={value}" for key, value in payload.items() if value is not None))
    return 0
