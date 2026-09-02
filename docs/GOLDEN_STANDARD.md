# Local Agent Golden Standard

This file records the current production invariants for `MichalMatu/local-agent`.

## Release/runtime invariants

- `main` is the production source of truth and normal installed runtime checkout.
- `agent_version.RELEASE_VERSION` matches the release tag `vX.Y.Z`.
- `v*-staging` branches/worktrees are temporary candidate-validation infrastructure and are removed after a release is established.
- The production multi-repository scheduler is `agent_parallel.py --max-workers 2`.
- `agent_multirepo.py` remains the unchanged serial fallback with concurrency one.
- Only one daemon/supervisor may hold the daemon lock.
- Shared supervisor polling/order/control primitives live under `local_agent/supervisor/`; the production parallel scheduler must not depend on the serial fallback entrypoint.

## Execution and recovery invariants

- The daemon is a deterministic executor, not a coding model.
- Every task has an immutable payload digest and one durable attempt claim.
- Interrupted tasks are never automatically replayed.
- Malformed/oversized task JSON is terminal input evidence.
- Command/no-output/task/RSS limits remain bounded.
- Already-running stages are not killed solely because the whole-task admission budget expires.
- Command output transport/retention is bounded.
- Every subprocess is registered and task commands use process groups.
- Successful commands may not leave background descendants.
- Graceful shutdown quiesces publication and terminates process groups with bounded escalation.
- Dirty workspaces are checkpointed before destructive cleanup.
- Final results are durably spooled before remote publication.
- Publication recovery republishes evidence without re-executing commands.
- Interrupted daemon-owned control metadata under status/runs/results/acks is recovered by exact path before control sync; unexpected task/control-request changes are never auto-cleaned.
- Self-update accepts validated fast-forward updates from a clean `main` checkout and rolls back validation failure.
- Self-update validation explicitly compiles the parallel production entrypoints and uses a bounded 600-second full-test margin.
- Terminal Git failures produce actionable diagnostics even when Git itself emitted no text.
- Control checkout recovery may remove only daemon-owned control artifacts plus explicitly allowlisted untracked host metadata (`.DS_Store`); every other unknown local change remains fatal.

## Operator observability invariants

- Successful routine control-plane Git synchronization/publication is quiet in the operator log; failures and retry diagnostics remain visible.
- The parallel supervisor emits a human-readable `IDLE` line after startup and after real task completion.
- A long-idle supervisor emits a bounded periodic `IDLE` heartbeat so `tail -f ~/Library/Logs/local-agent.log` remains immediately readable.
- Real parallel task boundaries are visible as `TASK START` / `TASK DONE`; low-level successful Git plumbing must not drown those operator events.
- Expected single control-repository lease contention is silent; repeated contention is logged only when the six-attempt bounded drain activates.
- Production launchd stdout/stderr logs are bounded: files above 2 MiB are compacted during an idle maintenance window to approximately the most recent 1 MiB while preserving append semantics.
- Multiline task commands are represented by concise stage/line/character descriptors in both legacy and `RuntimeExecutor` paths. Full command/output evidence remains in run/result JSON; `LOCAL_AGENT_VERBOSE_LOGS=1` is temporary diagnostic override only.

## Repository isolation invariants

- Repository ids and remote identities are unique case-insensitively.
- Normalized control/work/checkpoint paths are disjoint, including aliases and ancestor/descendant overlaps.
- Repository path globals are bound only inside short-lived workers.
- Claims, result spools, runs, corrupt claims and local status are repository-scoped.
- Every repository turn owns inherited OS execution leases for its id, remote and workspace paths through the lifetime of all descendants.
- Lease contention defers work/recovery without mutating repository state.
- Workers reject registry-entry changes after dispatch selection.
- Polling never implicitly clones, repairs or overwrites workspaces.

## Parallel resource invariants

- `resources` is mandatory for every task; invalid declarations are terminal contract errors rather than compatibility fallbacks.
- `resources: []` means no exclusive external resource beyond the repository lease and may be used for repository-local builds, tests, lint and analysis.
- Named resources are exclusive only among tasks sharing the same canonical name.
- `resources: ["machine"]` is reserved for genuine whole-host exclusivity.
- `memory_limit_mb` is an independent process-group RSS watchdog and never changes resource classification.
- Resource declarations are bounded to eight names and may not combine `machine` with another resource.
- Parallel tasks hold a shared machine lock; machine-exclusive tasks hold it exclusively.
- Machine/named resource descriptors are inherited into descendants and survive worker death until the last holder exits.
- Resource acquisition is nonblocking and occurs before claim/execution. Contention leaves the task pending and is retried with bounded backoff.
- Repository status exposes `waiting_resource` for blocked admission so remote planners do not mistake waiting for idle completion.
- Machine contention gets priority/drain fairness.
- Production recommendation is two workers; hard cap remains three.

## Global control invariants

- Repository workers never execute supervisor-wide restart/self-update.
- While workers run, maintenance may only probe for pending global control.
- Daemon control ids are restricted to ASCII letters, digits, `.`, `_` and `-`, with a 120-character maximum; ACK paths must remain under `.agent/daemon/acks/` after normalization.
- Control probes have explicit `CLEAR`, `PENDING`, `LEASE_BUSY` and `DEFERRED` outcomes; only a successful `CLEAR` probe advances the normal control-poll clock.
- A busy control-repository execution lease is `LEASE_BUSY`; transient sync/network/ACK-read failures are `DEFERRED`. Both retry promptly instead of being mistaken for "no request".
- After initial supervisor control service succeeds, ordinary `LEASE_BUSY` contention and `DEFERRED` failures do not immediately block unrelated repository admission. A confirmed `PENDING` request drains immediately, while six consecutive `LEASE_BUSY` probes force a bounded admission drain so global control cannot starve.
- A control ACK is durable only when it is visible on the fetched remote `agent-control` branch; a local-only ACK commit never suppresses replay of the remote request.
- A real global request stops new admission and waits for active workers to drain.
- Global control acquires all configured repository execution identities before running.
- Ordinary self-update waits for natural idle.
- Active registry identities are not removed/mutated while workers or descendants may remain alive.

## Planner and Chat Bridge invariants

- The Chrome Chat Bridge is wake-up/control transport only; ChatGPT remains the planner and Local Agent remains the deterministic executor.
- One autonomous conversation follows one active task at a time for its current goal and never queues a duplicate while that task is active.
- Planner sequencing is not global executor serialization: unrelated conversations/repositories may overlap when the parallel resource contract permits it.
- Every bridge wake-up re-reads repository-specific status/run/result evidence before deciding whether to wait, queue one next bounded task, pause for user action or stop a completed goal.
- Bridge `STOP`/`PAUSE` markers control the conversation loop only; they do not stop or reconfigure the Local Agent supervisor.
- An unfinished autonomous turn ends with `NEXT=<duration>`; `NEXT` arms or re-arms that conversation and schedules its next wake without overriding the global master switch.
- Resource/capacity waiting is a continuation state and must use `NEXT`, never `STOP`.

## Verification/release gate

A non-trivial runtime release requires:

1. an isolated staging candidate based on current `main`;
2. compile and pinned Ruff checks for release modules/tests;
3. full unittest/integration coverage;
4. real SIGTERM/SIGKILL process coverage when lifecycle/lease behavior changes;
5. real overlap, machine-exclusion and inherited-resource-lock coverage for parallel changes;
6. exact diff review;
7. green GitHub CI on the exact candidate SHA, including macOS smoke;
8. downstream planner-documentation audit for every registered repository when Local Agent contract/flow changed;
9. validated fast-forward of `main`;
10. matching `vX.Y.Z` tag;
11. production restart from `~/local-agent` on `main` and live version/revision/task verification;
12. staging worktree/branch cleanup after the release is established.

## Downstream contract

`AGENTS.md` defines the currently registered downstream documentation targets. A release is not operationally complete when those repositories materially describe an obsolete task schema, execution model, concurrency/resource contract, status/control surface or deployment flow.

Historical design notes remain references only and are not runtime contracts.

## Verification efficiency invariants

- Structured stages expose explicit `stream` and `summary` live-output policies without weakening retained result evidence.
- Successful noisy summary stages do not flood the operator log; failed summary stages expose a bounded tail.
- Explicit progress markers remain visible and heartbeat/watchdog enforcement stays active under summarized live output.

## Retry and logging invariants
- Unexpected worker exits use bounded 2-300 s exponential retry and reset after normal outcomes.
- Deferred global-control work uses bounded 2-15 s retry; six consecutive control-repository `LEASE_BUSY` probes force a bounded worker drain to prevent global-control starvation.
- Repeated outer supervisor failure/deferral notices are limited to one per 60 s for a continuing condition.
