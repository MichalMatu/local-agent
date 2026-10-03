# Local Agent Golden Standard

This file records the current release/runtime invariants for `MichalMatu/local-agent`. The source release marker is `v4.20.6`; the current production release is `v4.20.5` with Chat Bridge `0.8.1`, released from `main@bd793d60c3bce4b247deb80a7e2bfc88e8bf4373`. The 4.20.6 candidate adds deterministic production queue deduplication but has not yet advanced production. The deployed production release remains `v4.20.5` until the explicit release decision advances `main`. Candidate source must not be described as current production before the explicit release decision advances `main`. Production completed its natural self-update to the current 4.20.5 release revision during the 2026-10-04 self-diagnostic. A managed conversation is a transport/scheduling channel rather than a repository execution binding. Repository reasoning may span donor/target repositories without chat rebinding; executable `.agent/tasks` still require the exact canonical binding of the actual target repository. Conversation Fabric operator intake remains explicit runtime configuration and is currently not enabled/configured in production; child chats remain reasoning-only, and `.agent/tasks` retains all machine execution authority. Read the installed `self_revision` from live daemon status; never infer the deployed revision from a source checkout alone.

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
- Arbitrary non-empty unmarked Conversation Fabric lab roots are never silently adopted. The explicit profile-adoption path accepts only an isolated root containing exactly `browser-profile`, recognizable regular Chromium identity files and no symbolic links; it writes only inert lab directories plus the exact layout marker and does not rewrite browser-profile bytes.
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
