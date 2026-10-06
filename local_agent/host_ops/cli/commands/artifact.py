"""CLI for verified local artifact deployment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from local_agent.host_ops.capabilities.local.files import ArtifactDeploymentError, LocalArtifactDeployer


def run_deploy(
    source: str,
    destination_directory: str,
    *,
    destination_name: str | None,
    replace: bool,
    as_json: bool,
) -> int:
    try:
        result = LocalArtifactDeployer().deploy(
            Path(source),
            Path(destination_directory),
            destination_name=destination_name,
            replace=replace,
        )
    except ArtifactDeploymentError as exc:
        if as_json:
            print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        else:
            print(f"artifact deployment failed: {exc}", file=sys.stderr)
        return 1

    payload = result.as_dict()
    if as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(
            f"deployed {result.source} -> {result.destination} "
            f"sha256={result.sha256} size={result.size_bytes}"
        )
        if not result.directory_synced:
            print("warning: destination filesystem does not support directory fsync")
    return 0
