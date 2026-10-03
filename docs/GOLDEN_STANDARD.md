# Local Agent Golden Standard

This file records the current release/runtime invariants for `MichalMatu/local-agent`. The source release is `v4.20.5` with Chat Bridge `0.8.1`; the current production release is `v4.20.4`. The v4.20.5 candidate is not production yet: the deployed production release remains `v4.20.4` until the explicit release decision advances `main`. Candidate source must not be described as current production before the explicit release decision advances `main`. A managed conversation is a transport/scheduling channel rather than a repository execution binding. Repository reasoning may span donor/target repositories without chat rebinding; executable `.agent/tasks` still require the exact canonical binding of the actual target repository. Conversation Fabric operator intake remains explicit runtime configuration, child chats remain reasoning-only, and `.agent/tasks` retains all machine execution authority. Read the installed `self_revision` from live daemon status; never infer the deployed revision from a source checkout alone.

## Release/runtime invariants

- `main` is the production source of truth and normal installed runtime checkout.
- `local_agent.version.RELEASE_VERSION` names the prepared source release and, after release, the matching `vX.Y.Z` tag.
- A behavior-changing release has matching release notes and a changelog entry before final verification.
- Candidate branches/worktrees/staged runtime files are temporary validation infrastructure and are removed after production proof.
- Production multi-repository execution uses `agent_parallel.py --max-workers 4`; scheduler hard cap is four and default concurrency remains one.
- `agent_multirepo.py` remains serial fallback with concurrency one.
- Only one daemon/supervisor may hold the daemon lock.
- Shared scheduler/control/process ownership stays under the existing `local_agent` package boundaries; focused fixes must not add ad-hoc competing state machines.

## Execution and recovery invariants

- Local Agent is a deterministic executor, not a coding model.
- Executable task command strings containing the `codex` token are rejected before execution.
- Every task has an immutable payload digest and one durable attempt claim.
- Interrupted tasks are never automatically replayed.
- Malformed/oversized task JSON is terminal input evidence.
- Escape-safe `payload_file` references remain task-id scoped, bounded and resolved before normal validation/digesting.
- Command, no-output, whole-task and RSS limits remain bounded.
- Already-running stages are not killed only because later admission budget expired.
- Command output retention/transport is bounded.
- Task subprocesses use registered process groups; successful tasks may not leave background descendants.
- Graceful shutdown quiesces publication and terminates process groups with bounded escalation.
- Dirty workspaces are checkpointed before destructive cleanup.
- Final results are durably spooled before remote publication; publication recovery never re-executes commands.
- Unexpected local control/workspace changes are never silently cleaned.
- Self-update accepts only a validated fast-forward from a clean `main` checkout and rolls back validation failure.
- Self-update validation compiles production entrypoints and runs the bounded verification suite before restart.
- Control checkout recovery removes only daemon-owned control artifacts plus explicitly allowlisted host metadata.
- Arbitrary non-empty unmarked Conversation Fabric lab roots are never silently adopted. The explicit profile-adoption path accepts only an isolated root containing exactly `browser-profile`, recognizable regular Chromium identity files and no symbolic links; it writes only inert lab directories and the exact layout marker and does not rewrite browser-profile bytes.
- An adopted lab checkout identity may change only through the explicit fail-closed rebind path: the current marker must be canonical and healthy, mutable lab state directories must be empty, the new checkout must already exist and remain production-disjoint, and only the atomic layout marker may change.

## Repository/binding invariants

- Repository ids and remotes are unique case-insensitively.
- Normalized control/work/checkpoint paths are disjoint.
- Repository path globals are bound only inside short-lived workers.
- Claims/results/runs/status are repository-scoped.
- Workers hold inherited OS execution leases for repository identity/workspace for the full descendant lifetime.
- Lease contention defers without mutating repository state.
- Workers reject registry identity changes after dispatch selection.
- Polling never implicitly clones, repairs or overwrites project workspaces.
- Every Local Agent task carries the exact canonical `agent_binding` of its target repository.

## Parallel resource invariants

- `resources` is mandatory for every task; invalid declarations are terminal.
- `resources: []` means no exclusive external resource beyond repository lease.
- Named resources are exclusive only among tasks sharing the same canonical resource name.
- `resources: ["machine"]` is reserved for real whole-host exclusivity and may not be combined with another resource.
- `memory_limit_mb` is a separate process-group RSS watchdog, not a resource-classification mechanism.
- Resource acquisition is nonblocking and occurs before claim/execution; contention leaves the task pending.
- `waiting_resource` remains observable remote state.
- Machine contention retains drain/fairness semantics.
- Production concurrency is four workers; hard cap remains four.

## Global control invariants

- Repository workers never execute supervisor-wide restart/self-update.
- While workers run, maintenance may only probe pending global control.
- Daemon control ids are bounded/sanitized and ACK paths remain under `.agent/daemon/acks/`.
- Global-control probes distinguish `CLEAR`, `PENDING`, `LEASE_BUSY` and `DEFERRED`.
- Retry/backoff is bounded; only six genuinely consecutive control-repository `LEASE_BUSY` results trigger starvation protection.
- Known active control-worker contention pauses only new admission for that repository; unexplained ownership retains defensive global drain.
- A confirmed `PENDING` global request stops new admission and drains active workers.
- ACK is durable only when visible on the fetched remote control branch.
- Ordinary self-update waits for natural idle.
- Active registry identities are never removed/mutated while workers or descendants may still use them.

## MCP invariants

- Generic MCP protocol ownership remains under `local_agent/mcp/`.
- Supported Streamable HTTP endpoints are loopback-only (`127.0.0.1`, `::1`, `localhost`).
- Machine-local MCP registry/policy is not inferred from cwd or server-provided metadata.
- Discovery does not grant invocation authority.
- Every allowed tool has an explicit local risk class (`read`, `write`, `arbitrary_code`); consequential calls require matching explicit intent.
- Tool arguments/results/artifacts remain bounded and validated.
- Official MCP SDK owns protocol/framing/negotiation; Local Agent does not implement competing manual JSON-RPC framing.
- MCP stdio remains unsupported unless child-process lifecycle ownership becomes equally strong.
- MCP use remains outside task schema/scheduler policy: ordinary tasks invoke the bounded packaged MCP client/CLI.

## Planner and Chat Bridge invariants

### Role split

- ChatGPT remains the planner and source of coding decisions.
- GitHub is the durable control plane for task state and, for managed conversations, schedule desired state.
- Chat Bridge is bounded browser wake/delivery transport.
- Local Agent is the deterministic executor.
- The ChatGPT DOM is never repository identity and, for GitHub-managed chats, is not pacing/status authority.

### Superchat repository scope

- Every managed conversation has one concrete chat identity used for Bridge transport and GitHub-backed scheduling.
- The chat is not hard-bound to a repository for reasoning. The active user goal or durable Conversation Fabric request may name multiple donor and target repositories without Rebind.
- `repository_id` / `repository_ids` in reasoning requests are context only; they do not create machine authority.
- Legacy `planner_scope`, `repositoryId`, `agentBinding` and `bindingRevision` fields may remain in migrated Bridge state or the runtime catalog for compatibility/transport-workspace selection. They must not be interpreted as repository authorization.
- Before any executable work, resolve the actual target repository and create `.agent/tasks` only with that target's exact canonical `agent_binding`.
- Execution-disabled catalog targets may be inspected/reasoned about through allowed GitHub operations but may not receive Local Agent tasks; `local-agent` remains intentionally self-execution-disabled.
- The canonical `host-ops` entry remains the execution-enabled multirepo transport/host-operations workspace; it does not confer target-repository task authority.
- A planner must never invoke/delegate local Codex or another local coding-agent/LLM CLI through Local Agent.

### GitHub-backed schedule/status authority

For an exact managed `conversation_controls` record, GitHub is authoritative for:

- `STATUS`;
- `PAUSE`;
- `RESUME`;
- `NEXT`;
- `INTERVAL`.

Every schedule mutation increments `control_generation`; status reads do not. Schedule ownership is keyed by exact chat identity plus remote control generation and local conversation generation. Legacy repository/binding/revision fields are not schedule authority.

A confirmed `conversation_exhausted` state is terminal for that conversation safety epoch and must not be repaired away as GitHub schedule drift. `assistant_retry_exhausted` is likewise preserved against reconciliation of the already-applied remote generation; a strictly newer GitHub generation may serve as an explicit recovery decision. Manual `Run now` must not bypass confirmed conversation exhaustion.

The global Bridge Master switch is independent local operator state and is never changed by conversation desired state.

Legacy assistant schedule markers and user `OP:ENABLE` / `OP:DISABLE` / `OP:INTERVAL` are compatibility no-ops for a GitHub-managed chat. They must not be the normal scheduling path.

Legacy binding controls (`ADD`, `REBIND`) remain compatibility/migration paths only and must not be used for normal repository routing. `REMOVE` and Bridge maintenance remain explicit local controls.

### GitHub-control discovery

- Every MV3 service-worker activation ensures the dedicated one-minute GitHub-control alarm exists; install/startup performs the same idempotent initialization.
- The extension reads the existing public runtime endpoint and stores no GitHub credential.
- Remote runtime failure keeps last applied desired state and does not hand authority back to DOM controls.
- A paused conversation can discover a later GitHub `RESUME` even with no conversation wake alarm.

### Planner continuation discipline

- One conversation follows at most one active Local Agent task for its current goal; unrelated repositories may overlap under scheduler/resource rules.
- Every wake re-reads exact target status/run/result evidence before choosing the next action.
- Healthy active-task rechecks should be no sooner than about two minutes and normally 5-10 minutes for multi-minute builds/tests unless evidence supports a nearer check.
- If exact evidence proves the active task cannot succeed, cancel that exact task id and await cancellation/result evidence before replacing it.
- Resource/capacity waiting is continuation, not completion.
- An unfinished managed turn schedules continuation by incrementing GitHub `control_generation` and setting exact `next_wake_at` or interval state.
- Completed/release-validation work should leave the conversation PAUSED unless continued automation is explicitly required.

### Browser delivery and recovery

- Service-worker activation may refresh stale content/guard scripts but is not itself a conversation wake.
- Wake delivery must use the exact preferred conversation/tab, preserve operator composer edits and fail closed while ChatGPT generation is active.
- Immediately before submission Bridge re-resolves the current enabled Send button and clicks that live node; `form.requestSubmit()` is fallback only.
- Delivery is confirmed from the exact new user turn, not from click success alone.
- A retained Bridge prompt is reusable only if composer content is still exact.
- DOM inspection remains valid for composer/Send, generation Stop, submitted-user confirmation, structured Retry cards and conversation-length exhaustion.
- Recognized assistant terminal errors remain `Message delivery timed out. Please try again.` and `Resume stream unavailable`; unknown Retry-looking errors fail closed.
- Native Retry authorization remains exact-tab/conversation/binding/generation/enabled/Bridge-ownership scoped with bounded three-attempt budget.

## Operator observability invariants

- Routine successful Git synchronization/publication remains quiet; failures/retries remain visible.
- Parallel supervisor emits readable `IDLE` plus task boundary logs and bounded idle heartbeat.
- launchd stdout/stderr remains bounded.
- Multiline commands are logged by concise stage/size descriptors; full evidence stays in run/result JSON.
- `LOCAL_AGENT_VERBOSE_LOGS=1` is temporary diagnostics only.

## Architecture invariants

- `local_agent.supervisor.scheduling` owns deterministic scheduling policy/state decisions.
- `local_agent.supervisor.orchestrator` coordinates side effects and must not absorb another embedded scheduler state machine.
- Scheduling policy does not import Git/storage/subprocess/repository-worker implementations.
- `local_agent.repository.binding` owns canonical binding catalog/planner-scope validation.
- `local_agent.mcp` remains an independent generic boundary.
- Refactors preserve hard binding, claims/results, resource exclusion, emergency controls, self-update and process lifecycle semantics.

## Verification/release gate

A non-trivial runtime release requires:

1. isolated candidate from current `main`;
2. source release version, release notes and changelog entry before final verification, while candidate docs still identify actually deployed production separately;
3. focused positive/negative tests for changed state/policy;
4. lifecycle/lease/resource/MCP-specific real coverage where those boundaries change;
5. exact `main...candidate` architecture/dependency diff review;
6. full GitHub CI on exact candidate SHA: compile/Ruff/full unittest, coverage, Python 3.14 and real Bridge browser;
7. macOS ARM64 smoke on exact candidate SHA;
8. current-documentation/release-metadata contract checks;
9. downstream planner-documentation audit when a shared contract changes;
10. three independent pre-merge verification views: focused changed-policy evidence, full cross-platform CI and macOS exact-SHA smoke/recheck;
11. for Chat Bridge control changes, bounded live daily/diagnostic browser E2E using the exact production-shaped control path and ending PAUSED;
12. only then explicit merge/advance of `main`;
13. matching `vX.Y.Z` tag on released `main`;
14. restore a clean installed `~/local-agent` checkout, validated self-update/restart and live version/revision/task verification;
15. candidate branch/worktree/staging cleanup after production proof.

## Downstream contract

`AGENTS.md` defines registered downstream documentation targets. A release is not operationally complete when downstream planners materially describe an obsolete task schema, concurrency/resource model, status/control surface or deployment flow.

`docs/HOST_OPS_MULTIREPO.md` is the canonical transport-only multirepo planner guide. `docs/GITHUB_BRIDGE_CONTROL.md` is the canonical conversation pacing/status extension. Historical dated handoffs/release notes are evidence only.

## Retry/logging invariants

- Unexpected worker exits use bounded exponential retry and reset after normal outcomes.
- Deferred global-control work uses bounded retry.
- Degraded probes break consecutive lease-busy streaks.
- Known active-worker contention remains repository-local; unexplained contention may trigger bounded global drain.
