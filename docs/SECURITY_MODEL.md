# Security model

Local Agent is **execution infrastructure**, not a security sandbox. It is designed to make AI-assisted local execution explicit, bounded, attributable and recoverable. It does not make arbitrary commands safe and it does not attempt to isolate an intentionally malicious task from the host account that runs the agent.

> [!WARNING]
> Treat a task accepted by Local Agent as code execution with the permissions of the Local Agent operating-system user. Do not expose the task/control channels to principals you would not trust with that level of access.

## Trust boundaries

```mermaid
flowchart LR
    Planner["Planner / ChatGPT"]
    Bridge["Chat Bridge"]
    RepoControl["Repository agent-control"]
    Operator["operator-control"]
    Supervisor["Local Agent supervisor"]
    Worker["Bound repository worker"]
    Host["Local host + repositories"]

    Bridge --> Planner
    Planner -->|task intent| RepoControl
    RepoControl -->|validated task + binding| Supervisor
    Operator -->|global safety state| Supervisor
    Supervisor -->|admitted work| Worker
    Worker --> Host
```

The important boundaries are:

1. **Bridge → planner transport** — one concrete conversation identity owns delivery/scheduling only. Repository reasoning scope comes from the active goal or durable request; Bridge metadata never grants repository execution authority.
2. **Planner → control state** — planner intent becomes immutable task data for one exact target repository. A multirepo conversation still uses that target repository's canonical binding.
3. **Control state → executor** — schema, digest, repository identity, hard target binding and resource admission are checked before execution.
4. **Supervisor → worker** — repository work runs in short-lived isolated worker processes with process-group tracking and inherited execution/resource leases.
5. **Operator control → all work** — repository-independent emergency disable has precedence over normal task admission.

## What Local Agent protects

### Repository identity

One executable repository has one canonical opaque `agent_binding` UUID. Before claim/execution, the executor requires agreement between the machine-local registry, `.agent/binding.json` and the task binding. Missing or mismatched binding fails closed before task commands execute.

Chat Bridge conversation identity is transport/scheduling identity only. A parent Superchat may reason across multiple repositories, including donor and target repositories, without changing Bridge metadata. Natural-language repository names or durable `repository_id` / `repository_ids` fields are reasoning context, never executor authorization.

For executable work, the selected target must still resolve to a registered repository whose registry binding, `.agent/binding.json` binding and task `agent_binding` agree exactly. Execution-disabled targets cannot receive Local Agent tasks. Legacy `planner_scope` and conversation binding metadata may remain for compatibility or transport-workspace selection but are not security boundaries. See [`HOST_OPS_MULTIREPO.md`](HOST_OPS_MULTIREPO.md).

### Task identity and replay

- task payloads have immutable digests;
- a task id cannot silently acquire a different payload inside one repository;
- malformed task data becomes terminal evidence instead of an implicit retry;
- an interrupted claimed task is never silently replayed;
- terminal result publication is recoverable independently from command execution.

These rules reduce accidental duplicate execution and make recovery auditable.

### Bounded execution

Runtime commands use bounded output transport, process groups and command/no-output/whole-task/RSS controls. Repository and external-resource leases prevent conflicting work from being admitted concurrently and survive worker failure through spawned descendants.

These are **reliability and containment bounds**, not an operating-system sandbox.

### Git publication

Publication stages exact paths rather than using broad `git add -A`. Repository control clones are infrastructure state, and normal work is queued through the repository `agent-control` branch rather than by editing daemon-owned control clones manually.

### Emergency control

The global disable path is independent of project repositories. The guarded entrypoint observes the central `operator-control` branch and persists a local disabled marker. A remote request can disable the agent, but remote state cannot clear the local marker; re-enable is an explicit local action.

Repository-scoped `cancel_task` requires the exact task id. Runtime reset is allowed only while disabled and removes only local ephemeral runtime state.

See [`EMERGENCY_CONTROLS.md`](EMERGENCY_CONTROLS.md).

## What Local Agent does not protect against

Local Agent currently does **not** claim to provide:

- a VM/container/macOS sandbox for task commands;
- filesystem isolation from everything accessible to the Local Agent user;
- network egress isolation;
- secret redaction from arbitrary command output;
- protection against a deliberately malicious task authored by a trusted control-plane principal;
- multi-tenant hostile-code isolation.

If any of these become requirements, they should be added as explicit executor-side mechanisms rather than inferred from the existing watchdog and worker model.

## Fail-closed rules

The executor intentionally refuses or terminally rejects work when identity or task-contract evidence is invalid. Important examples include:

- missing repository binding;
- mismatched registry/control/task binding;
- malformed task JSON;
- invalid resource declarations;
- changed repository configuration between scheduling and dispatch;
- malformed persistent disable state.

Bridge schedule/delivery validation remains fail closed for invalid conversation or control state, but Bridge repository metadata is not executor authorization. No chat state is accepted as substitute evidence for the target repository binding.

Unexpected checkout state is not automatically overwritten. Self-update must validate before restart and roll back on validation failure.

## Operator checklist

Before enabling autonomous execution:

- verify the running daemon revision/status rather than relying only on the checkout;
- keep repository bindings and the local registry intentional and unique; treat Bridge planner-scope/binding metadata as compatibility state only;
- keep `operator-control` available as an independent stop path;
- do not share control-plane write access with untrusted principals;
- treat credentials available to the Local Agent OS user as potentially available to executed tasks;
- for the currently registered project repositories, use `resources: []` for project-dedicated hardware and verify the intended device/port inside the task; reserve named resources for genuinely shared external hardware/state and `machine` for true whole-host exclusivity;
- preserve the release verification gates in [`../AGENTS.md`](../AGENTS.md).

## Security changes

A change to binding, planner scope, task validation, process lifecycle, emergency controls, Git publication, resource locking, self-update, global control admission/drain policy or command execution is security-relevant even when it is not branded as a security feature. Such changes require targeted positive and negative regression coverage plus the broader release checks described in [`../AGENTS.md`](../AGENTS.md).

> [!IMPORTANT]
> When a safety property matters, encode it in the executor and test it. Planner instructions and documentation are supporting controls, not enforcement boundaries.
