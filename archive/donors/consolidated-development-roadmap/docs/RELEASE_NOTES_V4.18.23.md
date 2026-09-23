# Local Agent 4.18.23

## Summary

Add `MichalMatu/host-ops` as a canonical execution-enabled hard-bound repository without changing scheduler, executor, task-schema, resource, process-lifecycle, self-update or Chat Bridge protocol behavior.

`host-ops` is the deterministic capability repository used for bounded local host operations such as system OpenSSH/Termux and, in later phases, ADB, browser and macOS automation. Planning remains in ChatGPT and execution remains bounded by Local Agent.

## Canonical repository identity

- Repository id: `host-ops`
- Repository: `MichalMatu/host-ops`
- Agent binding: `16d688b6-b0ef-4905-a5bd-24e59c99cfb4`
- Execution enabled: `true`
- Control branch: `agent-control`
- Default source branch: `main`

The identity is added to `config/agent_bindings.json` and mirrored exactly in `chat_bridge/runtime.example.json`. Binding regression coverage verifies the catalog/runtime identity and preserves catalog uniqueness checks.

## Remote control-plane preparation

The `MichalMatu/host-ops` repository has a dedicated remote `agent-control` branch containing only Local Agent control-plane state. Its `.agent/binding.json` carries the exact repository id, repository name and canonical UUID above, alongside empty task/result/run/status/daemon-ack directories.

This release does not claim that a specific Mac has already appended the new local repository-registry entry. Executor-side onboarding remains fail-closed until the machine-local registry contains the same identity and the independent control/work checkouts have been provisioned and validated.

## Deployment boundary

The safe activation sequence remains:

1. install/update Local Agent source containing this canonical catalog entry;
2. globally disable Local Agent admission;
3. append the `host-ops` registry entry without reordering existing repositories;
4. run the existing repository provisioner so separate control/work/checkpoint paths are created;
5. validate checkout identity and the `.agent/binding.json` match;
6. re-enable Local Agent;
7. publish the same `host-ops` identity to live `chat-bridge-state` runtime;
8. explicitly bind/rebind the intended Chat Bridge conversation to repository id `host-ops`;
9. execute a read-only onboarding smoke before consequential host operations.

No step may substitute the `local-agent` infrastructure binding, which remains `execution_enabled: false`.

## Resource policy

The initial `host-ops` tasks use `resources: []` unless a concrete future operation genuinely requires a shared named resource or whole-machine exclusivity. SSH/ADB/device access alone does not imply `resources: ["machine"]`; target identity must be established inside the task/capability.

## Compatibility

The source-tree change is intentionally limited to canonical onboarding/configuration, regression coverage and release metadata. Existing repositories, binding UUIDs and their order are unchanged. Chat Bridge extension/content protocol versions remain unchanged from 4.18.22.

A live Termux smoke is deliberately not claimed by this source release. It requires the machine-local registry plus SSH trust/key state and is recorded only after those real prerequisites are verified.
