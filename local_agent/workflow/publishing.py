from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from local_agent.runtime.task_contract import task_digest, validate_task
from local_agent.workflow import contract


def child_task_id(
    workflow_id: str,
    node_id: str,
    manifest_digest: str,
) -> str:
    contract.validate_workflow_id(workflow_id)
    if not isinstance(node_id, str) or not node_id:
        raise ValueError("workflow node id must be a non-empty string")
    if not isinstance(manifest_digest, str) or not manifest_digest.startswith("sha256:"):
        raise ValueError("manifest_digest must be a sha256 digest")
    payload = json.dumps(
        [workflow_id, node_id, manifest_digest],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "wf-" + hashlib.sha256(payload).hexdigest()


def _task_node(manifest: dict[str, Any], node_id: str) -> dict[str, Any]:
    contract.validate_workflow_manifest(manifest)
    for node in manifest["nodes"]:
        if node["id"] != node_id:
            continue
        if node["kind"] != "task":
            raise ValueError(f"workflow node {node_id!r} is not a task node")
        return node
    raise ValueError(f"unknown workflow node: {node_id!r}")


def materialize_child_task(
    manifest: dict[str, Any],
    node_id: str,
) -> dict[str, Any]:
    node = _task_node(manifest, node_id)
    manifest_digest = contract.manifest_digest(manifest)
    task = copy.deepcopy(node["task"])
    task["id"] = child_task_id(str(manifest["id"]), node_id, manifest_digest)
    task["agent_binding"] = node["agent_binding"]
    task["workflow"] = {
        "id": manifest["id"],
        "node_id": node_id,
        "manifest_digest": manifest_digest,
    }
    validate_task(task, require_agent_binding=True)
    return task


def materialized_task_digest(
    manifest: dict[str, Any],
    node_id: str,
) -> str:
    return task_digest(materialize_child_task(manifest, node_id))
