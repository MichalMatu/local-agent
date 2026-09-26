# Local Agent 4.18.26

## Summary

Add `MichalMatu/hardware-lab` as a canonical execution-enabled hard-bound repository without changing scheduler, executor, task-schema, resource, process-lifecycle, self-update or Chat Bridge protocol behavior.

`hardware-lab` is the shared repository for isolated hardware experiments under `projects/`. The immediate downstream use is `projects/kobra2-neo`, while repository execution remains generic and project-specific device semantics stay in the project itself.

## Canonical repository identity

- Repository id: `hardware-lab`
- Repository: `MichalMatu/hardware-lab`
- Agent binding: `fa3dc1d7-5ee2-4b59-841c-e41918610df1`
- Execution enabled: `true`
- Control branch: `agent-control`
- Default source branch: `main`

The identity is added to `config/agent_bindings.json` and mirrored exactly in `chat_bridge/runtime.example.json`. Dedicated regression coverage verifies the catalog/runtime identity and preserves catalog uniqueness checks.

## Deployment boundary

Activation remains fail-closed and uses the existing multi-repository administration path:

1. release/update Local Agent source containing this canonical catalog entry;
2. globally disable Local Agent admission;
3. append the `hardware-lab` machine-registry entry without reordering existing repositories;
4. run the existing repository provisioner so separate control/work/checkpoint paths are created;
5. commit the matching `.agent/binding.json` to `hardware-lab/agent-control` and validate checkout/binding identity;
6. publish the same identity to live `chat-bridge-state` runtime;
7. re-enable Local Agent;
8. explicitly rebind/add the intended ChatGPT conversation to repository id `hardware-lab` and require a fresh bootstrap before repository work;
9. execute a read-only onboarding smoke before consequential hardware operations.

No step may substitute the `host-ops` or `local-agent` binding. `host-ops` remains a generic execution dependency for local machine/device primitives, while `hardware-lab` owns Kobra-specific code, CAD, calibration and project policy.

## Resource policy

Initial `hardware-lab` tasks use `resources: []` unless a concrete shared external resource or whole-machine operation requires otherwise. Repository execution leases already serialize tasks within `hardware-lab`; device identity is verified inside each task immediately before use.

## Compatibility

The source-tree change is limited to canonical onboarding/configuration, regression coverage and release metadata. Existing repository identities and binding UUIDs remain unchanged and in the same order. Chat Bridge extension/content protocol versions are unchanged from 4.18.25.
