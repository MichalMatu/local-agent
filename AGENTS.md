# Local Agent repository rules

This repository is execution infrastructure. Prefer deterministic behavior, bounded execution, explicit failure and recoverable state over clever recovery.

## Execution contract

- All machine-generated execution content is English-only: source, comments, identifiers, tests, documentation, prompts, task metadata, runtime logs, shell-visible status text and commit messages.
- Interactive ChatGPT conversation language is independent from that execution contract.
- `local_agent/daemon/service.py` owns daemon lifecycle, durable claims/results, remote status/control and self-update. `local_agent/paths.py` resolves the installed checkout independently of cwd.
- `local_agent/supervisor/orchestrator.py` owns bounded-parallel supervisor side-effect orchestration and directly consumes `local_agent/supervisor/scheduling.py`.
- `local_agent/supervisor/serial.py` owns the direct serial fallback with global concurrency one.
- `local_agent/version.py` owns the release version.
- `local_agent/config.py` owns startup-loaded timeout configuration.
- `local_agent/mcp/` owns generic machine-local MCP registry validation, loopback Streamable HTTP client sessions, explicit tool policy, bounded discovery/execution, artifact persistence and the packaged MCP CLI. Application-specific MCP workflows do not belong in Local Agent.
- `local_agent/host_ops/` owns absorbed deterministic host/remote capability execution. Its dependency direction remains `cli -> workflows -> capabilities -> core`; it must not own planning, repository routing, scheduling, task admission, Conversation Fabric policy or daemon lifecycle.
- `local_agent/foundation/core.py` owns deterministic task execution, workspace preparation/checkpointing and result publication.
- `local_agent/foundation/process.py` owns registered spawning, bounded stdout transport, process groups, durable text writes and inherited execution-lease descriptors.
- `local_agent/foundation/storage.py` owns bounded control Git sync, transient-network retry and storage diagnostics.
- `local_agent/repository/binding.py` owns canonical immutable agent/repository binding identities, planner-scope catalog policy, control-binding validation and registry migration.
- `local_agent/repository/context.py` owns repository registry parsing, workspace identity/config digests and repository lease keys.
- `local_agent/repository/admin.py` owns explicit repository provisioning and checkout validation.
- `local_agent/repository/cleanup.py` owns bounded runtime/control metadata cleanup.
- `local_agent/repository/worker.py` owns one short-lived process-isolated repository turn, hard binding admission and repository-scoped controls.
- `local_agent/runtime/executor.py` owns staged command lifecycle, watchdog orchestration and task execution budgets.
- `local_agent/runtime/task_contract.py` owns immutable task digests, task-schema limits/validation, agent-binding task validation and bounded task timeout/memory parsing.
- `local_agent/runtime/progress.py` owns validated progress-marker parsing and bounded asynchronous progress publication.
- `local_agent/runtime/output.py` owns live command-output rendering, unified-diff collapsing and bounded summary-failure tails.
- `local_agent/runtime/telemetry.py` owns host/process telemetry parsing and collection plus process-group RSS sampling.
- `local_agent/operator/local.py` owns the persistent fail-closed disable marker, disabled-only runtime reset and binding migration.
- `local_agent/operator/remote.py` owns repository-independent remote emergency desired-state polling and fail-closed validation.
- `local_agent/entrypoint.py` owns the guarded service lifecycle, remote operator polling and safe supervisor start/stop/reexec.
- `local_agent/cli/diagnostics.py` owns diagnostics/status/task inspection. The daemon must not depend on diagnostics.
- `local_agent/supervisor/resources.py` owns external machine/named-resource flock arbitration and inherited resource descriptors used by the parallel worker.
- `local_agent/supervisor/policy.py` owns shared adaptive polling/order/time policy.
- `local_agent/supervisor/scheduling.py` owns pure production retry/backoff/due/max-worker policy and control-probe retry/admission state/classification; do not duplicate that policy in the orchestrator.
- `local_agent/supervisor/worker.py` owns parallel worker task admission/dispatch and hard-binding admission.
- `local_agent/platform/macos_launchd.py` owns portable macOS LaunchAgent generation/lifecycle helpers. Machine-specific plist content must not be committed.
- Root Python files are limited to four operational launchers: `agentd.py`, `agent_entrypoint.py`, `agent_parallel.py` and `agent_multirepo.py`. Existing launchd definitions and in-flight self-update/restart paths require these filenames. They contain no implementation or import aliases.
- `tests/test_package_layout.py` enforces the launcher allowlist, source bound, packaged imports and executable path behavior. Internal code and tests import packaged owners directly.
- Worker subprocesses use `python -m local_agent.supervisor.worker` or `python -m local_agent.repository.worker` with explicit checkout cwd. Restarts use absolute supported launcher paths and preserve supervisor mode/options. Changes require behavior-preserving tests.

## Safety invariants

- One executable repository has one canonical opaque `agent_binding` UUID. Repository id, repository remote and binding are operational identity, not planner hints.
- Before claim/execution, both parallel and serial repository workers require local registry `agent_binding == .agent/binding.json agent_binding == task.agent_binding`.
- Missing repository binding is fail-closed `unbound`; invalid/mismatched control binding is fail-closed `binding_error`; missing/wrong task binding is a terminal pre-claim rejection and must execute no task command.
- Global operator `disabled` state takes precedence over repository binding admission so emergency stop remains authoritative during partial migrations or broken binding state.
- Chat Bridge conversation identity is transport/scheduling identity only. It never grants repository execution authority and normal repository routing must not depend on chat Rebind.
- Repository ids named in the active user goal or durable Conversation Fabric request are reasoning context. A parent Superchat may reason across donor and target repositories without rebinding; every executable Local Agent task still uses the exact canonical binding of its actual target repository.
- Runtime `planner_scope` and legacy conversation binding metadata remain compatibility/transport-workspace metadata only. They are not authorization evidence for repository work.
- Local Agent is the sole product-level brain/orchestrator. Host operations are implemented by the absorbed `local_agent.host_ops` subsystem and execute through the `local-agent` target. The standalone `MichalMatu/host-ops` repository is a frozen donor/history repository, is absent from the canonical execution catalog, and must not receive new executable tasks.
- The `local-agent` catalog entry is execution-enabled and may receive executable project work only under its exact canonical binding. Self-execution does not weaken registry/control/task binding equality, repository leases, global emergency controls, or any task/resource limits.
- MCP server identity and authorization are machine-local explicit configuration. Discovery never grants execution permission; unknown servers/tools, disabled policies and non-loopback endpoints fail closed.
- MCP `write` and `arbitrary_code` tools require both a matching local risk policy and matching explicit invocation intent. Server-provided tool names, descriptions and annotations are not authorization evidence.
- MCP stdio is unsupported until it can use the existing registered spawn/process-group lifecycle contract; an SDK must never spawn an unregistered daemon child.
- MCP textual results and binary artifacts must remain bounded. Binary content must be MIME-validated and persisted as bounded artifact metadata rather than unbounded base64 task output.
- Never automatically replay a task after daemon/process interruption.
- Never silently reuse a task id for a different payload within one repository.
- Task/result/claim identity is repository-scoped; identical task ids in different repositories must not collide.
- Malformed task JSON is terminal `invalid_task_file`, not a retry candidate.
- Keep command/no-output/RSS watchdogs and the whole-task admission budget intact unless a change explicitly replaces them with an equivalent or stronger mechanism.
- Command stdout transport and retained result capture must remain strictly bounded.
- Never terminate an already-running stage solely because the whole-task admission budget expired.
- Never mutate repository path globals in a long-lived supervisor. Legacy path binding is allowed only inside a short-lived repository worker process.
- Repository ids and remote identities are case-insensitively unique. Agent bindings are canonical lowercase UUIDs and unique. Control/work/checkpoint paths must be disjoint after normalization, alias and ancestor/descendant checks.
- A repository turn holds OS execution leases for its id, remote and every workspace path. Those descriptors must survive supervisor and worker failure through every spawned descendant.
- Stale-claim recovery must not inspect or mutate a repository while an earlier process still owns any matching execution lease.
- A worker must reject dispatch when its exact repository configuration changed after the supervisor selected it.
- Every daemon, supervisor and worker subprocess must use the shared registered spawn path so termination cannot race an unregistered child.
- Repository polling never implicitly clones, overwrites or repairs a checkout. Provisioning is explicit.
- Repository workers must never execute global daemon restart/self-update directly.
- Remote daemon control ids must use only ASCII letters, digits, `.`, `_` and `-`, with a 120-character maximum, and generated ACK paths must remain under `.agent/daemon/acks/` after normalization.
- All daemon self-updates must validate before restart and roll back on validation failure.
- Self-update installs the inspected commit under the installation lock. A durable pending-installation journal blocks supervisor startup and local enable after interrupted validation until explicit operator recovery.
- Keep Git staging path-exact; never use `git add -A` in publication logic.
- Preserve ignored build caches unless a task explicitly requests a clean rebuild.
- Never destroy a dirty disposable workspace without first creating a recoverable checkpoint outside the worktree.
- Treat repository control clones as daemon infrastructure. Queue normal work through the remote `agent-control` branch rather than hand-editing those clones.

## Production scheduling invariants

The bounded-parallel production coordinator is `local_agent/supervisor/orchestrator.py`; pure policy/state belongs to `local_agent/supervisor/scheduling.py`:

- production `max_workers` is `4` and the hard cap remains `4`;
- default remains `1`;
- `agent_multirepo.py` remains the known-safe serial fallback and preserves the same hard binding admission contract;
- serial and parallel supervisors share the same daemon lock and must never run simultaneously;
- one repository has at most one active worker process at a time;
- independent repositories may overlap only after repository and external-resource admission succeeds;
- worker subprocesses inherit only the execution/resource lease descriptors required for their repository turn;
- retry/backoff/resource waiting remains bounded and never mutates immutable task payloads;
- global control probing may pause only the control repository after proven repeated control-lease ownership; unrelated repositories remain eligible unless the defensive unknown-owner global-drain path is required;
- a confirmed pending global restart/self-update request drains all new admission before maintenance;
- Conversation Fabric operator campaigns, when explicitly enabled, run outside repository/resource leases and must not create a second scheduler.

## Verification expectations

- Keep `python scripts/verify.py` green for normal changes and use focused tests first when practical.
- Use `python scripts/verify.py --profile macos-smoke` for release/installation/runtime boundary changes.
- Bridge changes require the focused Node suite plus browser/DOM contract coverage when the content/transport boundary changes.
- Transport/repository-routing releases additionally require positive/negative coverage proving chat metadata cannot grant execution authority, selected target task bindings remain exact, execution-disabled targets remain non-executable, and parallel/serial executor binding admission is unchanged.
- Release metadata/version/changelog/docs must agree before tagging.
