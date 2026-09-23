#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from local_agent.repository.context import load_repository_registry
from local_agent.workflow import contract, methods, preview, revisions, store
from local_agent.workflow.activation import (
    WorkflowRevisionActivationStore,
    activation_digest,
)
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.git_cancellation import GitWorkflowCancellationTransport
from local_agent.workflow.git_control_plane import GitWorkflowControlPlane
from local_agent.workflow.lineage_cycle import run_lineage_cycle
from local_agent.workflow.lineage_operator import activate_next_lineage_revision
from local_agent.workflow.revision_store import WorkflowRevisionStore


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _load_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON file must contain an object")
    return payload


def _effective_store(workflow_store: store.WorkflowStore) -> WorkflowEffectiveStateStore:
    revision_store = WorkflowRevisionStore(workflow_store)
    activation_store = WorkflowRevisionActivationStore(
        workflow_store,
        revision_store,
    )
    return WorkflowEffectiveStateStore(
        workflow_store,
        revision_store,
        activation_store,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect and manage Local Agent workflows.")
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Override the Local Agent application state directory.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        help="Override the existing Local Agent repository registry path.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("methods", help="List built-in workflow methods.")

    method_parser = subparsers.add_parser(
        "method",
        help="Show one built-in workflow method and its pinned digest.",
    )
    method_parser.add_argument("name")
    method_parser.add_argument("--version", type=int)

    validate_parser = subparsers.add_parser(
        "validate-manifest",
        help="Validate a workflow manifest without executing it.",
    )
    validate_parser.add_argument("path", type=Path)

    preview_parser = subparsers.add_parser(
        "preview-manifest",
        help="Preview task waves and waits without persisting or executing the workflow.",
    )
    preview_parser.add_argument("path", type=Path)

    submit_parser = subparsers.add_parser(
        "submit",
        help="Persist an immutable local workflow without dispatching repository tasks.",
    )
    submit_parser.add_argument("path", type=Path)

    subparsers.add_parser("list", help="List persisted local workflow ids.")

    show_parser = subparsers.add_parser("show", help="Show one persisted workflow.")
    show_parser.add_argument("workflow_id")

    append_revision_parser = subparsers.add_parser(
        "append-revision",
        help="Append one immutable continuation record without dispatching it.",
    )
    append_revision_parser.add_argument("workflow_id")
    append_revision_parser.add_argument("path", type=Path)

    revisions_parser = subparsers.add_parser(
        "revisions",
        help="Show the append-only revision lineage for one workflow.",
    )
    revisions_parser.add_argument("workflow_id")

    effective_parser = subparsers.add_parser(
        "preview-effective",
        help="Preview the base manifest plus persisted revisions without executing it.",
    )
    effective_parser.add_argument("workflow_id")

    activations_parser = subparsers.add_parser(
        "activations",
        help="Show persisted revision activation records without mutating workflow state.",
    )
    activations_parser.add_argument("workflow_id")

    effective_state_parser = subparsers.add_parser(
        "effective-state",
        help="Show isolated effective revision state without dispatching or mutating it.",
    )
    effective_state_parser.add_argument("workflow_id")

    activate_next_parser = subparsers.add_parser(
        "activate-next",
        help="Explicitly activate exactly one next persisted workflow revision.",
    )
    activate_next_parser.add_argument("workflow_id")

    run_cycle_parser = subparsers.add_parser(
        "run-cycle",
        help="Run exactly one explicit Git-backed workflow reconciliation cycle.",
    )
    run_cycle_parser.add_argument("workflow_id")

    resolve_effective_gate_parser = subparsers.add_parser(
        "resolve-effective-gate",
        help="Resolve one user gate in the active effective revision graph.",
    )
    resolve_effective_gate_parser.add_argument("workflow_id")
    resolve_effective_gate_parser.add_argument("node_id")
    resolve_effective_gate_parser.add_argument("decision")
    resolve_effective_gate_parser.add_argument("--resolver", default="local-operator")

    resolve_effective_checkpoint_parser = subparsers.add_parser(
        "resolve-effective-checkpoint",
        help="Resolve one planner checkpoint in the active effective revision graph.",
    )
    resolve_effective_checkpoint_parser.add_argument("workflow_id")
    resolve_effective_checkpoint_parser.add_argument("node_id")
    resolve_effective_checkpoint_parser.add_argument(
        "--resolver",
        default="chatgpt-planner",
    )
    resolve_effective_checkpoint_parser.add_argument("--note")

    cancel_effective_parser = subparsers.add_parser(
        "cancel-effective",
        help="Request cancellation of the active effective revision graph.",
    )
    cancel_effective_parser.add_argument("workflow_id")

    resolve_parser = subparsers.add_parser(
        "resolve-gate",
        help="Resolve one waiting user gate with an exactly-once durable decision.",
    )
    resolve_parser.add_argument("workflow_id")
    resolve_parser.add_argument("node_id")
    resolve_parser.add_argument("decision")
    resolve_parser.add_argument("--resolver", default="local-operator")

    checkpoint_parser = subparsers.add_parser(
        "resolve-checkpoint",
        help="Resolve one planner checkpoint after explicit evidence review.",
    )
    checkpoint_parser.add_argument("workflow_id")
    checkpoint_parser.add_argument("node_id")
    checkpoint_parser.add_argument("--resolver", default="chatgpt-planner")
    checkpoint_parser.add_argument("--note")

    cancel_parser = subparsers.add_parser(
        "cancel",
        help="Request workflow cancellation without killing unrelated work.",
    )
    cancel_parser.add_argument("workflow_id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "methods":
        for spec in methods.list_builtin_methods():
            print(
                f"{spec['name']}\tversion={spec['version']}\t"
                f"{methods.method_digest(spec)}"
            )
        return 0

    if args.command == "method":
        try:
            spec = methods.load_builtin_method(args.name, version=args.version)
        except ValueError as exc:
            _print_json({"error": str(exc)})
            return 2
        _print_json(
            {
                "name": spec["name"],
                "version": spec["version"],
                "digest": methods.method_digest(spec),
                "spec": spec,
            }
        )
        return 0

    if args.command == "validate-manifest":
        try:
            payload = _load_object(args.path)
            contract.validate_workflow_manifest(payload)
            digest = contract.manifest_digest(payload)
        except Exception as exc:
            _print_json(
                {
                    "valid": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return 2
        _print_json(
            {
                "valid": True,
                "workflow_id": payload["id"],
                "manifest_digest": digest,
                "node_count": len(payload["nodes"]),
            }
        )
        return 0

    if args.command == "preview-manifest":
        try:
            payload = _load_object(args.path)
            result = preview.preview_workflow(payload)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json(
            {
                "workflow_id": payload["id"],
                "waves": [list(wave) for wave in result.waves],
                "final_state": result.final_state,
                "waiting_nodes": list(result.waiting_nodes),
            }
        )
        return 0

    workflow_store = store.WorkflowStore(args.state_dir)

    if args.command == "submit":
        try:
            payload = _load_object(args.path)
            result = workflow_store.submit(payload)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json(result)
        return 0

    if args.command == "list":
        _print_json({"workflow_ids": workflow_store.workflow_ids()})
        return 0

    if args.command == "show":
        try:
            manifest = workflow_store.load_manifest(args.workflow_id)
            current_state = workflow_store.load_state(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json({"manifest": manifest, "state": current_state})
        return 0

    if args.command == "activate-next":
        try:
            result = activate_next_lineage_revision(
                workflow_store,
                args.workflow_id,
            )
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json(result)
        return 0

    if args.command == "run-cycle":
        try:
            if args.registry is not None and not args.registry.is_file():
                raise ValueError(
                    f"explicit repository registry is unavailable: {args.registry}"
                )
            repositories = load_repository_registry(path=args.registry)
            effective_store = _effective_store(workflow_store)
            control_plane = GitWorkflowControlPlane()
            cancellation_transport = GitWorkflowCancellationTransport(control_plane)
            result = run_lineage_cycle(
                effective_store,
                args.workflow_id,
                repositories,
                control_plane,
                cancellation_transport,
            )
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json(
            {
                "workflow_id": args.workflow_id,
                "execution": {
                    "published": list(result.execution.published),
                    "reconciled": list(result.execution.reconciled),
                    "deferred_same_repository": list(
                        result.execution.deferred_same_repository
                    ),
                    "deferred_unrelated_work": list(
                        result.execution.deferred_unrelated_work
                    ),
                    "integrity_failures": list(result.execution.integrity_failures),
                },
                "cancellation": {
                    "requested": list(result.cancellation.requested),
                    "deferred": list(result.cancellation.deferred),
                    "accepted": list(result.cancellation.accepted),
                    "completed": list(result.cancellation.completed),
                    "rejected": list(result.cancellation.rejected),
                    "not_needed": list(result.cancellation.not_needed),
                },
            }
        )
        return 0

    if args.command == "resolve-effective-gate":
        try:
            effective_store = _effective_store(workflow_store)
            decision = effective_store.resolve_user_gate(
                args.workflow_id,
                args.node_id,
                args.decision,
                resolver=args.resolver,
            )
            current_state = effective_store.load(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json({"decision": decision, "effective_state": current_state})
        return 0

    if args.command == "resolve-effective-checkpoint":
        try:
            effective_store = _effective_store(workflow_store)
            resolution = effective_store.resolve_planner_checkpoint(
                args.workflow_id,
                args.node_id,
                resolver=args.resolver,
                note=args.note,
            )
            current_state = effective_store.load(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json({"resolution": resolution, "effective_state": current_state})
        return 0

    if args.command == "cancel-effective":
        try:
            effective_store = _effective_store(workflow_store)
            current_state = effective_store.cancel(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json({"effective_state": current_state})
        return 0

    if args.command in {
        "append-revision",
        "revisions",
        "preview-effective",
        "activations",
        "effective-state",
    }:
        revision_store = WorkflowRevisionStore(workflow_store)

        if args.command == "append-revision":
            try:
                record = _load_object(args.path)
                saved = revision_store.append(args.workflow_id, record)
                base = workflow_store.load_manifest(args.workflow_id)
                chain = revision_store.load(args.workflow_id)
            except Exception as exc:
                _print_json({"error": f"{type(exc).__name__}: {exc}"})
                return 2
            _print_json(
                {
                    "revision": saved,
                    "revision_digest": revisions.revision_digest(saved),
                    "tip_digest": revisions.lineage_tip_digest(base, chain),
                    "revision_count": len(chain),
                }
            )
            return 0

        if args.command == "revisions":
            try:
                base = workflow_store.load_manifest(args.workflow_id)
                chain = revision_store.load(args.workflow_id)
            except Exception as exc:
                _print_json({"error": f"{type(exc).__name__}: {exc}"})
                return 2
            _print_json(
                {
                    "workflow_id": args.workflow_id,
                    "base_manifest_digest": contract.manifest_digest(base),
                    "tip_digest": revisions.lineage_tip_digest(base, chain),
                    "revisions": [
                        {
                            "revision": record["revision"],
                            "digest": revisions.revision_digest(record),
                            "parent_digest": record["parent_digest"],
                            "checkpoint_node_id": record["checkpoint_node_id"],
                            "node_ids": [node["id"] for node in record["nodes"]],
                        }
                        for record in chain
                    ],
                }
            )
            return 0

        if args.command == "activations":
            try:
                activation_store = WorkflowRevisionActivationStore(
                    workflow_store,
                    revision_store,
                )
                records = activation_store.load(args.workflow_id)
            except Exception as exc:
                _print_json({"error": f"{type(exc).__name__}: {exc}"})
                return 2
            _print_json(
                {
                    "workflow_id": args.workflow_id,
                    "activation_count": len(records),
                    "activations": [
                        {
                            "revision": record["revision"],
                            "digest": activation_digest(record),
                            "revision_digest": record["revision_digest"],
                            "parent_tip_digest": record["parent_tip_digest"],
                            "checkpoint_node_id": record["checkpoint_node_id"],
                            "new_node_states": record["new_node_states"],
                            "activated_at": record["activated_at"],
                        }
                        for record in records
                    ],
                }
            )
            return 0

        if args.command == "effective-state":
            try:
                effective_store = _effective_store(workflow_store)
                current = effective_store.load(args.workflow_id)
            except Exception as exc:
                _print_json({"error": f"{type(exc).__name__}: {exc}"})
                return 2
            _print_json(
                {
                    "workflow_id": args.workflow_id,
                    "effective_state": current,
                }
            )
            return 0

        try:
            base = workflow_store.load_manifest(args.workflow_id)
            chain = revision_store.load(args.workflow_id)
            effective = revision_store.effective_manifest(args.workflow_id)
            result = preview.preview_workflow(effective)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json(
            {
                "workflow_id": args.workflow_id,
                "base_manifest_digest": contract.manifest_digest(base),
                "revision_count": len(chain),
                "tip_digest": revisions.lineage_tip_digest(base, chain),
                "node_count": len(effective["nodes"]),
                "waves": [list(wave) for wave in result.waves],
                "final_state": result.final_state,
                "waiting_nodes": list(result.waiting_nodes),
            }
        )
        return 0

    if args.command == "resolve-gate":
        try:
            decision = workflow_store.resolve_user_gate(
                args.workflow_id,
                args.node_id,
                args.decision,
                resolver=args.resolver,
            )
            current_state = workflow_store.load_state(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json({"decision": decision, "state": current_state})
        return 0

    if args.command == "resolve-checkpoint":
        try:
            resolution = workflow_store.resolve_planner_checkpoint(
                args.workflow_id,
                args.node_id,
                resolver=args.resolver,
                note=args.note,
            )
            current_state = workflow_store.load_state(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json({"resolution": resolution, "state": current_state})
        return 0

    if args.command == "cancel":
        try:
            result = workflow_store.cancel(args.workflow_id)
        except Exception as exc:
            _print_json({"error": f"{type(exc).__name__}: {exc}"})
            return 2
        _print_json(result)
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
