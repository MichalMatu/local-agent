# Multi-Repository Design

This document defines the production design for one `local-agent` service operating several repositories with isolated state and bounded resource-aware parallelism.

## Production schedulers

`agent_parallel.py` is the recommended multi-repository supervisor. Production uses `--max-workers 4`, which is also the scheduler hard cap.

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

The first enabled registry entry is the supervisor control repository in registry v1. Reordering enabled entries therefore changes the global restart/self-update/status control source; treat registry order as operational identity.

Provisioning is explicit:

```bash
python -m local_agent.repository.admin list
python -m local_agent.repository.admin validate
python -m local_agent.repository.admin provision --repository-id <id>
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

Repository exclusion and machine-resource exclusion are deliberately separate. A task never needs to declare its repository as a resource: the repository execution lease already guarantees that two tasks for the same configured repository cannot execute concurrently.

## Parallel resource admission

Every task must declare `resources` explicitly. The declaration describes only external/shared machine resources used in addition to the task's automatic repository lease.

Canonical runtime rules:

- `resources: []` means no exclusive external resource; repository-local work may overlap with other repositories;
- named resources are exclusive per exact canonical name and may overlap with unrelated named resources;
- `resources: ["machine"]` means true full-machine exclusivity and must be declared alone;
- resource names are canonical lowercase strings using letters, digits, `.`, `_`, `:`, and `-`;
- duplicate resource names, malformed declarations, missing `resources`, and declarations longer than eight names are invalid task payloads rather than compatibility fallbacks.

The currently registered project repositories intentionally use:

```json
{"resources": []}
```

for all executable project work, including their project-dedicated hardware operations. The task command discovers and verifies the intended device/port at runtime. Named resources remain available for future genuinely shared external resources; they are not required merely because a task touches hardware dedicated to one repository.

The machine lock remains a useful global gate. Every non-machine task holds it shared, allowing normal tasks to overlap. A true `machine` task takes it exclusive, waits for all normal holders to drain and prevents new normal admission until it can run.

`memory_limit_mb` is independent from resource classification. It remains the per-task RSS watchdog limit and does not silently promote a task to full-machine exclusivity. The supervisor does not reserve or sum task memory limits during admission. A separate global memory-reservation scheduler should be added only if measured host pressure justifies it.

Resource acquisition is immediate/nonblocking inside a repository worker. A worker that cannot acquire a resource exits without claiming or executing the selected task. The task remains pending and the supervisor retries it automatically. This prevents a stale pre-claim task snapshot while providing durable waiting semantics.

## Durable resource waiting

Resource contention is a wait state, not a task failure and not completion of an autonomous goal.

When a selected task cannot acquire a named or machine resource, repository status is published as:

```json
{
  "state": "waiting_resource",
  "current_task_id": null,
  "pending_task_id": "example-task",
  "blocked_resources": ["shared-resource"],
  "waiting_since": "...",
  "retrying": true,
  "execution_variant": "parallel"
}
```

The first wait timestamp is preserved while the same task remains blocked on the same resource. Repeated identical waits do not need a new remote status commit on every retry.

Once admission succeeds, repository status becomes `running` with `current_task_id` and `active_resources`, then normal terminal result handling resumes.

Resource contention uses bounded retry backoff of approximately 2, 5, 10, 30 and then 60 seconds. Normal long-running production supervision continues retrying indefinitely while the task remains pending. Repository-execution-lease/configuration deferrals remain separate short retries.

Machine-exclusive contention retains priority/drain behavior: the supervisor stops admitting unrelated normal work, lets current workers finish and retries the blocked machine task alone so true global work cannot starve. Named-resource contention never drains unrelated repositories.

`--once` remains a bounded diagnostic mode and may terminate after its bounded deferral budget; it is not the durability model used by the long-running production supervisor.

## Scheduling

Production: `max_workers=4`; hard cap: `4`; default: `1`.

One repository still has only one active repository worker/task at a time. Different repositories may overlap whenever their declared external resources permit it. Independent repository builds or hardware tasks using dedicated project devices therefore do not serialize merely because they perform similar work.

The scheduler retains adaptive/fair polling and bounded worker turns. One repository failure, lease contention or configuration change must not terminate polling of other repositories.

## Global control

Restart, self-update and global status are supervisor-wide operations.

While workers run, the supervisor probes the designated control repository for a pending valid request. Probe outcomes distinguish `CLEAR`, `PENDING`, `LEASE_BUSY` and degraded `DEFERRED` failures. A detected `PENDING` request stops new admissions immediately. Before executing global control, the supervisor acquires execution identities for every currently configured repository, which also catches surviving workers/descendants from an earlier supervisor process.

The frozen v4.18.13 baseline has confirmed BUG-002: if the control repository itself has a long-running active worker, the periodic control probe cannot acquire that worker's repository lease. After six consecutive `LEASE_BUSY` outcomes, v4.18.13 forces a global admission drain. This can delay unrelated `resources: []` repositories even though worker capacity remains available. The candidate fix must treat lease ownership by the supervisor's own known active control-repository worker as expected and continue unrelated admission, while retaining bounded defensive handling for unexplained lease holders and immediate drain for confirmed `PENDING` control.

Ordinary maintenance/self-update waits for a natural idle window. Production self-update runs from the clean `main` checkout.

Do not remove or identity-mutate registry entries while a worker/descendant may still be alive; a completely removed old identity cannot be included in the current-registry all-lease check.

## Crash and shutdown behavior

SIGTERM stops active task work, quiesces control-Git publication and terminates registered process groups with bounded escalation. SIGKILL cannot run cleanup handlers; inherited repository and resource descriptors remain the safety boundary until the final surviving descendant exits.

Interrupted claimed work is not automatically replayed. Completed durable results may be republished without rerunning commands.

## Planner contract

Separate ChatGPT conversations may queue tasks independently in different repositories. An autonomous Chat Bridge conversation follows one active task at a time for its current goal; this planner sequencing does not globally serialize the executor, so unrelated repository tasks may overlap when resource admission permits it.

Every queued task must classify resources explicitly. For the currently registered execution-enabled project repositories, executable project work uses:

```json
{"resources": []}
```

including project-dedicated hardware operations. Device/port detection and verification happen inside the task command. Use a named resource only for a genuinely shared external resource that can conflict across repositories, and use `resources: ["machine"]` only for true whole-host exclusivity.

Installing or mutating a shared toolchain may use a dedicated named resource such as `toolchain:platformio` or `toolchain:esp-idf`. Merely compiling with an already installed toolchain does not require that lock.

When status is `waiting_resource`, the planner must not queue a replacement task, stop the autonomous goal or require user intervention merely because admission is delayed. The executor is already retrying the same immutable pending task.

The real `.agent/status/daemon.json`, exact run evidence and terminal task results are the authority for the running version/execution model.

## Validation evidence

Parallel scheduler releases require:

- task-contract tests for explicit canonical resources;
- real temporary-Git two-repository software overlap;
- a long-lived control-repository overlap test that crosses the global-control probe interval and proves a second `resources: []` repository starts before the first finishes;
- real named-resource overlap/exclusion behavior when named resources are changed;
- real machine-exclusion behavior;
- real resource-wait status followed by automatic execution after resource release without a new task payload;
- real POSIX inherited-resource-FD lifetime after worker death;
- exact-SHA Linux compile/Ruff/full tests;
- exact-SHA macOS process/multi-repository/parallel smoke;
- downstream planner-documentation synchronization.

## Deployment and rollback

Production code runs from `~/local-agent` on `main`. The frozen known-working v4.18.13 rollback identity is:

```text
v4.18.13
= a32e54858c3bcb9687334b3232b71ae6ff130208
= rollback/v4.18.13-known-working
```

Use the generated macOS LaunchAgent configuration for bounded parallel mode. The serial mode remains a direct rollback path and uses the same label.

Candidate branches/worktrees are release-candidate infrastructure only. After a validated candidate is fast-forwarded to `main`, tagged and verified live from `main`, remove obsolete staging worktrees/branches.
