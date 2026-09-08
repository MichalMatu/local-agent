# Local Agent Golden Standard

This file records the release/runtime invariants for `MichalMatu/local-agent`. The source release is `v4.18.19` and the current production release is `v4.18.19`. The 4.18.19 change is a repository-onboarding/config release: `MichalMatu/local-climate-link-starter` was added with canonical binding `e75c77cb-7589-4452-94b2-decc97ff85a1`, the local registry/control binding and live Chat Bridge runtime were aligned, and a read-only smoke task completed successfully against target `main` SHA `99f565711fdffb4e9b4e2be0289620da359d65a4`. No scheduler, executor, parallel-supervisor, Chat Bridge extension, or content-protocol behavior changed. `v4.18.18` remains the immutable rollback point for the prior runtime/browser release, with `rollback/v4.18.18-production-validated` preserving its exact validated implementation point.

## Release/runtime invariants

- `main` is the production source of truth and normal installed runtime checkout.
- `local_agent.version.RELEASE_VERSION` names the release prepared by the current source tree and, after release, the `vX.Y.Z` tag.
- Candidate source must not be described as current production before the explicit release decision advances `main`.
- A behavior-changing release must have matching `docs/RELEASE_NOTES_V<version>.md` and `docs/CHANGELOG.md` entries before verification can pass.
- Candidate branches/worktrees are temporary validation infrastructure and are removed after a release is established.
- Production multi-repository execution uses `agent_parallel.py --max-workers 4`; the scheduler hard cap is four and the default remains one.
- `agent_multirepo.py` remains the serial fallback with concurrency one.
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
- Self-update validation explicitly compiles the production entrypoints and runs the bounded full test suite before restart.
- Terminal Git failures produce actionable diagnostics even when Git itself emitted no text.
- Control checkout recovery may remove only daemon-owned control artifacts plus explicitly allowlisted untracked host metadata (`.DS_Store`); every other unknown local change remains fatal.

## Operator observability invariants

- Successful routine control-plane Git synchronization/publication is quiet in the operator log; failures and retry diagnostics remain visible.
- The parallel supervisor emits a human-readable `IDLE` line after startup and after real task completion.
- A long-idle supervisor emits a bounded periodic `IDLE` heartbeat so `tail -f ~/Library/Logs/local-agent.log` remains readable.
- Real parallel task boundaries are visible as `TASK START` / `TASK DONE`; low-level successful Git plumbing must not drown those events.
- Single expected control-repository lease contention is silent. Repeated known-worker contention logs the control-repository admission pause; repeated unexplained contention logs the defensive global drain.
- Production launchd stdout/stderr logs are bounded: files above 2 MiB are compacted during an idle maintenance window to approximately the most recent 1 MiB while preserving append semantics.
- Multiline task commands are represented by concise stage/line/character descriptors. Full command/output evidence remains in run/result JSON; `LOCAL_AGENT_VERBOSE_LOGS=1` is a temporary diagnostic override only.

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
- `resources: []` means no exclusive external resource beyond the repository lease.
- The currently registered project repositories intentionally use `resources: []` for executable project work, including project-dedicated hardware operations; device and port identity is verified inside task commands.
- Named resources remain available for genuinely shared external resources and are exclusive only among tasks sharing the same canonical name.
- `resources: ["machine"]` is reserved for genuine whole-host exclusivity.
- `memory_limit_mb` is an independent process-group RSS watchdog and never changes resource classification or performs aggregate host-memory admission.
- Resource declarations are bounded to eight names and may not combine `machine` with another resource.
- Parallel tasks hold a shared machine lock; machine-exclusive tasks hold it exclusively.
- Machine/named resource descriptors are inherited into descendants and survive worker death until the last holder exits.
- Resource acquisition is nonblocking and occurs before claim/execution. Contention leaves the task pending and is retried with bounded backoff.
- Repository status exposes `waiting_resource` for blocked admission so remote planners do not mistake waiting for idle completion.
- Machine contention gets priority/drain fairness.
- Production concurrency is four workers; the hard cap remains four.

## Global control invariants

- Repository workers never execute supervisor-wide restart/self-update.
- While workers run, maintenance may only probe for pending global control.
- Daemon control ids are restricted to ASCII letters, digits, `.`, `_` and `-`, with a 120-character maximum; ACK paths must remain under `.agent/daemon/acks/` after normalization.
- Control probes have explicit `CLEAR`, `PENDING`, `LEASE_BUSY` and `DEFERRED` outcomes; only successful control recovery advances the normal control-poll clock.
- A busy control-repository execution lease is `LEASE_BUSY`; transient sync/network/ACK-read failures are `DEFERRED`. Neither is treated as "no request".
- Control retry uses bounded 2-15 second backoff. Overall deferred-probe count and **consecutive `LEASE_BUSY` streak** are separate state.
- A `DEFERRED` outcome resets the consecutive lease-busy streak while preserving bounded retry/backoff. Therefore only six genuinely consecutive `LEASE_BUSY` outcomes can trigger lease-busy starvation protection.
- Fewer than six consecutive `LEASE_BUSY` outcomes retry without changing repository admission.
- Six consecutive `LEASE_BUSY` outcomes while the designated control repository is a known active worker pause only **new admission for that control repository**. Existing workers continue and unrelated repositories remain admissible when worker/resource capacity permits.
- The pause prevents a continuous control-repository task queue from reacquiring its own lease forever. Once the active control worker releases the lease, the supervisor gets an opportunity to probe global control before another control-repository task starts.
- Six consecutive `LEASE_BUSY` outcomes with no matching known active control worker retain the defensive **global drain** for unexplained/stale lease ownership.
- A confirmed `PENDING` global request always stops new admission and drains active workers immediately.
- `CLEAR`, successful full control service, explicit disable/re-enable recovery, or a configured control-repository identity change clears stale retry/lease-busy/pause evidence as appropriate.
- Reordering the registry so a different first enabled repository becomes global control invalidates the previous control-poll clock so the new source is checked promptly.
- A control ACK is durable only when it is visible on the fetched remote `agent-control` branch; a local-only ACK commit never suppresses replay of the remote request.
- Global control acquires all configured repository execution identities before running.
- Ordinary self-update waits for natural idle.
- Active registry identities are not removed/mutated while workers or descendants may remain alive.

## Architecture invariants

- `local_agent.supervisor.scheduling` owns deterministic scheduling state and pure decisions: due/retry/backoff, max-worker policy and control-probe retry/admission classification.
- `local_agent.supervisor.orchestrator` coordinates side effects: reading probe outcomes, starting/reaping workers, invoking global drain/service, status publication and shutdown.
- Scheduling policy must not import daemon, Git/storage, subprocess/process management or repository worker implementations.
- Do not solve a focused scheduler defect by adding another embedded state machine to `orchestrator.py` or by creating a new miscellaneous helper module without a stable ownership boundary.
- Refactors must preserve hard binding, claims/results, resource exclusion, emergency controls, self-update and process lifecycle semantics.

## Planner and Chat Bridge invariants

- The Chrome Chat Bridge is wake-up/control transport only; ChatGPT remains the planner and Local Agent remains the deterministic executor.
- One autonomous conversation follows one active task at a time for its current goal and never queues a duplicate while that task is active.
- Planner sequencing is not global executor serialization: unrelated conversations/repositories may overlap when the parallel resource contract permits it.
- Every bridge wake-up re-reads repository-specific status/run/result evidence before deciding whether to wait, queue one next bounded task, cancel one exact doomed active task, pause for user action or stop a completed goal.
- Bridge `STOP`/`PAUSE` markers control the conversation loop only; they do not stop or reconfigure the Local Agent supervisor.
- `NEXT=30s` remains protocol-compatible for explicit operator/emergency use, but autonomous polling of a healthy active task must not use 30-second cadence.
- The first healthy-task liveness re-check should be no sooner than about two minutes; multi-minute builds/tests should normally use 5-10 minute `NEXT` pacing unless exact evidence supports a nearer completion.
- If exact run/status evidence already proves an active task cannot achieve its intended outcome, the planner should publish repository-scoped `cancel_task` for that exact task id and wait for cancellation/result evidence before replacing it.
- An unfinished autonomous turn ends with `NEXT=<duration>`; `NEXT` arms or re-arms that conversation and schedules its next wake without overriding the global master switch.
- Resource/capacity waiting is a continuation state and must use `NEXT`, never `STOP`.
- Chat Bridge content protocol version is owned only by `control_protocol.js`; worker, content, popup and test harness must consume that shared value rather than declare independent versions.
- Popup tab activation and stale-content replacement are worker-owned; popup must not maintain a second `chrome.scripting.executeScript`/protocol-mismatch implementation.
- Chat Bridge content protocol upgrades must be replaceable in already-open tabs without requiring a normal manual ChatGPT reload when the older content script is still reachable.
- Service-worker activation probes configured open ChatGPT tabs and re-injects content only when unavailable or protocol-mismatched; activation itself must not send a wake, mutate binding/schedule state, or act as a scheduling event.
- Transient assistant-control delivery failures use bounded retry/backoff and must not permanently exhaust after a fixed small number of attempts.
- A Bridge-owned prompt retained after `send_button_not_ready` or `delivery_unconfirmed` may be reused only when the composer still matches the exact prompt; any operator edit blocks automatic reuse.
- Immediately before submission Bridge must re-resolve the current enabled ChatGPT Send button and use its live DOM `click()` path as the primary action; `form.requestSubmit()` may be used only as a last-resort fallback and never with a stale button reference.
- Assistant-safe LAB inspection/diagnostic commands may return Bridge-generated read-only evidence into the same conversation but must never change repository binding or grant executor/repository-write authority.
- `LAB:OP:*` mutations are accepted only from user-authored ChatGPT messages in the exact top-frame conversation; assistant messages cannot execute the operator namespace.
- Global `CHATS`/cross-chat routing inspection is available only from the `local-agent` infrastructure binding; ordinary project chats remain current-chat scoped.
- LAB operator-command dedupe is persistent and bounded independently from conversation state so onboarding/removal/reload controls do not replay across extension/content reloads.

## Verification/release gate

A non-trivial runtime release requires:

1. an isolated candidate based on current `main`;
2. matching source release version, release notes and changelog before final verification; candidate documentation must still name the actually deployed production release separately until the explicit release decision;
3. focused compile/lint plus positive and negative tests for the changed policy/state transitions;
4. real SIGTERM/SIGKILL process coverage when lifecycle/lease behavior changes;
5. real overlap, machine-exclusion and inherited-resource-lock coverage for parallel changes;
6. for BUG-002, a real temporary-Git control-repository task that crosses the six-consecutive-`LEASE_BUSY` threshold and proves another `resources: []` repository starts before the control task ends;
7. exact `main...candidate` diff and architecture/dependency review;
8. full GitHub CI on the exact candidate SHA: compile/Ruff/full unittest, coverage, Python 3.14 and Bridge browser;
9. macOS ARM64 smoke on the exact candidate SHA containing both pure control-admission policy coverage and the real BUG-002 overlap regression;
10. current-documentation drift/release-metadata contract checks;
11. downstream planner-documentation audit for every registered repository when Local Agent contract/flow changed;
12. three independent pre-merge verification passes recorded for the exact final SHA: focused policy/integration evidence, full cross-platform CI matrix, and macOS exact-SHA smoke/recheck;
13. only then an explicit decision to advance `main`;
14. matching `vX.Y.Z` tag on released `main`;
15. production restart/self-update from `~/local-agent` on `main` and live version/revision/task verification;
16. candidate branch/worktree cleanup after the release is established.

## Downstream contract

`AGENTS.md` defines the currently registered downstream documentation targets. A release is not operationally complete when those repositories materially describe an obsolete task schema, execution model, concurrency/resource contract, status/control surface or deployment flow.

Historical design notes remain references only and are not runtime contracts.

## Verification efficiency invariants

- Structured stages expose explicit `stream` and `summary` live-output policies without weakening retained result evidence.
- Successful noisy summary stages do not flood the operator log; failed summary stages expose a bounded tail.
- Explicit progress markers remain visible and heartbeat/watchdog enforcement stays active under summarized live output.

## Retry and logging invariants

- Unexpected worker exits use bounded 2-300 s exponential retry and reset after normal outcomes.
- Deferred global-control work uses bounded 2-15 s retry.
- Only six **consecutive** control-repository `LEASE_BUSY` outcomes trigger lease-busy starvation protection; degraded probe outcomes break that streak.
- Known-active-worker contention pauses only new control-repository admission; unexplained contention retains bounded global drain.
- Repeated outer supervisor failure/deferral notices are limited to one per 60 s for a continuing condition.
