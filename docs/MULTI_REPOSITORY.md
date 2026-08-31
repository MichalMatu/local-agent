# Multi-Repository Design v4.11

This document defines the production design for one `local-agent` service operating several repositories with isolated state and bounded resource-aware parallelism.

## Production schedulers

`agent_parallel.py` is the recommended v4.11 multi-repository supervisor. Production uses `--max-workers 2`.

`agent_multirepo.py` remains the direct serial fallback with global execution concurrency one. Both supervisors:

- own the same daemon lock;
- use the same registry and repository workspaces;
- spawn short-lived repository workers;
- preserve repository-scoped claims/results/status;
- share the validated task execution core.

They are replacement execution modes, never simultaneous services.

## Registry

Machine-local configuration:

```text
~/Library/Application Support/local-agent/repositories.json
```

Each entry defines a repository id, remote identity and control/work/checkpoint workspaces. Repository ids/remotes are unique case-insensitively and normalized workspace paths must be disjoint, including aliases and ancestor/descendant relationships.

Provisioning is explicit:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
python agent_repo_admin.py provision --repository-id <id>
```

Polling never implicitly clones, repairs or overwrites a checkout.

## Worker isolation

A supervisor never binds repository-specific `agent_core` paths in its long-lived process. Each short-lived worker:

1. receives one repository id plus the expected immutable registry-entry digest;
2. validates inherited repository execution leases;
3. validates the selected registry entry and existing checkouts;
4. binds repository paths only inside the worker process;
5. syncs that repository's `agent-control` branch;
6. performs recovery/control checks;
7. executes at most one pending task;
8. publishes repository-scoped status/result evidence and exits.

Repository execution leases cover repository id, remote and control/work/checkpoint identities. Their descriptors are inherited through spawned descendants, so a supervisor/worker crash cannot permit unsafe stale-claim recovery while old work is still alive.

## Parallel resource admission

Parallelism is opt-in per task, not inferred from commands.

Effective resource rules:

- omitted/malformed/oversized `resources` => `machine` exclusive;
- `resources: []` => software-only parallel admission;
- named resources => exclusive lock per declared name plus shared machine lock;
- `machine` => exclusive machine lock;
- non-machine admission requires `memory_limit_mb` enabled and <=1024 MiB;
- maximum resource declaration length is eight names.

The machine lock is shared by admitted parallel tasks and exclusive for machine tasks. Named resource locks serialize tasks that share the same resource. All resource descriptors are inherited into command descendants.

Resource acquisition is immediate/nonblocking. A worker that cannot acquire its resources exits without claiming/executing the selected task and the supervisor retries later. This prevents stale pre-claim task snapshots.

Machine-exclusive contention triggers priority/drain mode: the supervisor stops admitting unrelated work, lets currently running workers finish and retries the blocked machine task alone. Named-resource contention uses bounded retry without blocking unrelated repositories.

## Scheduling

Production recommendation: `max_workers=2`; hard cap: `3`; default: `1`.

One repository still has only one active repository worker/task at a time. Different repositories may overlap only when resource admission permits it.

The scheduler retains adaptive/fair polling and bounded worker turns. One repository failure, lease contention or configuration change does not terminate polling of other repositories.

## Global control

Restart, self-update and global status are supervisor-wide operations.

While workers run, the supervisor only probes the designated control repository for a pending valid request. A detected request stops new admissions and waits for tracked workers to drain. Before executing global control, the supervisor acquires execution identities for every currently configured repository, which also catches surviving workers/descendants from an earlier supervisor process.

Ordinary maintenance/self-update waits for a natural idle window. Production self-update runs from the clean `main` checkout.

Do not remove or identity-mutate registry entries while a worker/descendant may still be alive; a completely removed old identity cannot be included in the current-registry all-lease check.

## Crash and shutdown behavior

SIGTERM stops active task work, quiesces control-Git publication and terminates registered process groups with bounded escalation. SIGKILL cannot run cleanup handlers; inherited repository and resource descriptors remain the safety boundary until the final surviving descendant exits.

Interrupted claimed work is not automatically replayed. Completed durable results may be republished without rerunning commands.

## Planner contract

Separate ChatGPT conversations may queue tasks independently in different repositories. An autonomous Chat Bridge conversation follows one active task at a time for its current goal; this planner sequencing does not globally serialize the executor, so unrelated repository tasks may overlap when resource admission permits it.

Planners must classify resources conservatively:

- software-only lightweight checks can use `resources: []` plus a bounded memory limit;
- hardware/USB/serial/flashing/unknown heavy tooling remains machine-exclusive by omitting `resources`;
- named resources should be used only when the shared-machine interaction is understood.

The real `.agent/status/daemon.json` and task results are the authority for the running version/execution model.

## Validation evidence

v4.11 release validation includes:

- unit coverage for resource normalization, control probing and one-shot deferrals;
- real temporary-Git two-repository overlap integration;
- real machine-exclusion behavior;
- real POSIX inherited-resource-FD lifetime after worker death;
- exact-SHA Linux compile/Ruff/full tests;
- exact-SHA macOS process/multi-repository/parallel smoke;
- real Mac live overlap and machine-exclusion smoke with two registered repositories.

The detailed audit/live record is retained in `PARALLEL_EXECUTION_PLAN.md`.

## Deployment and rollback

Production code runs from `~/local-agent` on `main`. Use `deploy/macos/com.michal.local-agent.parallel.plist` for bounded parallel mode. The serial plist remains a direct rollback path and uses the same label.

Staging branches/worktrees are release-candidate infrastructure only. After a validated candidate is fast-forwarded to `main`, tagged and verified live from `main`, remove obsolete staging worktrees/branches.
