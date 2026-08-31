# Local Agent Golden Standard v4.11

This file records the current production invariants for `MichalMatu/local-agent`.

## Release/runtime invariants

- `main` is the production source of truth and normal installed runtime checkout.
- `agent_version.RELEASE_VERSION` matches the release tag `vX.Y.Z`.
- `v*-staging` branches/worktrees are temporary candidate-validation infrastructure and are removed after a release is established.
- The recommended v4.11 multi-repository scheduler is `agent_parallel.py --max-workers 2`.
- `agent_multirepo.py` remains the unchanged serial fallback with concurrency one.
- Only one daemon/supervisor may hold the daemon lock.

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

- Missing, malformed or oversized `resources` is full `machine` exclusivity.
- `resources: []` is an explicit planner assertion that the task is software-only and safe to overlap.
- Named resources are exclusive among tasks sharing the name.
- Any non-machine task requires enabled `memory_limit_mb <= 1024`; otherwise it falls back to `machine` exclusivity.
- Resource declarations are bounded to eight names.
- Parallel tasks hold a shared machine lock; machine-exclusive tasks hold it exclusively.
- Machine/named resource descriptors are inherited into descendants and survive worker death until the last holder exits.
- Resource acquisition is nonblocking and occurs before claim/execution; resource contention never creates a long unclaimed stale-task wait.
- Machine contention gets priority/drain fairness.
- Production recommendation is two workers; hard cap remains three.

## Global control invariants

- Repository workers never execute supervisor-wide restart/self-update.
- While workers run, maintenance may only probe for pending global control.
- Control probes have explicit `CLEAR`, `PENDING` and `DEFERRED` outcomes; only a successful `CLEAR` probe advances the normal control-poll clock.
- A busy control-repository lease or transient probe/ACK-read failure is `DEFERRED` and is retried promptly instead of being mistaken for "no request".
- A control ACK is durable only when it is visible on the fetched remote `agent-control` branch; a local-only ACK commit never suppresses replay of the remote request.
- A real global request stops new admission and waits for active workers to drain.
- Global control acquires all configured repository execution identities before running.
- Ordinary self-update waits for natural idle.
- Active registry identities are not removed/mutated while workers or descendants may remain alive.

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
