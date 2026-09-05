# Local Agent repository rules

This repository is execution infrastructure. Prefer deterministic behavior, bounded execution, explicit failure and recoverable state over clever recovery.

## Execution contract

- All machine-generated execution content is English-only: source, comments, identifiers, tests, documentation, prompts, task metadata, runtime logs, shell-visible status text and commit messages.
- Interactive ChatGPT conversation language is independent from that execution contract.
- `agentd.py` owns the root daemon lifecycle, durable claims/results, remote status/control and self-update. Its root location is operational because restart/self-update paths are location-sensitive.
- `agent_parallel.py` owns released bounded-parallel supervisor orchestration and current production scheduling semantics. Its root location is currently operational because worker/restart paths are location-sensitive.
- `agent_multirepo.py` remains the direct serial fallback with global concurrency one and a location-sensitive root restart path.
- `local_agent/version.py` owns the release version. Root `agent_version.py` is a compatibility module alias only.
- `local_agent/config.py` owns startup-loaded timeout configuration. Root `agent_config.py` is a compatibility module alias only.
- `local_agent/foundation/core.py` owns deterministic task execution, workspace preparation/checkpointing and result publication. Root `agent_core.py` is a compatibility module alias only.
- `local_agent/foundation/process.py` owns registered spawning, bounded stdout transport, process groups, durable text writes and inherited execution-lease descriptors. Root `agent_process.py` is a compatibility module alias only.
- `local_agent/foundation/storage.py` owns bounded control Git sync, transient-network retry and storage diagnostics. Root `agent_storage.py` is a compatibility module alias only.
- `local_agent/repository/binding.py` owns canonical immutable agent/repository binding identities, control-binding validation and registry migration. Root `agent_binding.py` is a compatibility module alias only.
- `local_agent/repository/context.py` owns repository registry parsing, workspace identity/config digests and repository lease keys. Root `agent_repository.py` is a compatibility module alias only.
- `local_agent/repository/admin.py` owns explicit repository provisioning and checkout validation. Root `agent_repo_admin.py` is an executable/module shim only.
- `local_agent/repository/cleanup.py` owns bounded runtime/control metadata cleanup. Root `agent_cleanup.py` is a compatibility module alias only.
- `local_agent/repository/worker.py` owns one short-lived process-isolated repository turn, hard binding admission and repository-scoped controls. Root `agent_repo_worker.py` is an executable/module shim only.
- `local_agent/runtime/executor.py` owns staged command lifecycle, watchdog orchestration and task execution budgets. Root `agent_runtime.py` is a compatibility module alias only.
- `local_agent/runtime/task_contract.py` owns immutable task digests, task-schema limits/validation, agent-binding task validation and bounded task timeout/memory parsing.
- `local_agent/runtime/progress.py` owns validated progress-marker parsing and bounded asynchronous progress publication.
- `local_agent/runtime/output.py` owns live command-output rendering, unified-diff collapsing and bounded summary-failure tails.
- `local_agent/runtime/telemetry.py` owns host/process telemetry parsing and collection plus process-group RSS sampling.
- `local_agent/operator/local.py` owns the persistent fail-closed disable marker, disabled-only runtime reset and binding migration. Root `agent_operator.py` is the executable/module shim.
- `local_agent/operator/remote.py` owns repository-independent remote emergency desired-state polling and fail-closed validation. Root `agent_remote_operator.py` is a compatibility module alias only.
- `local_agent/entrypoint.py` owns the guarded service lifecycle, remote operator polling and safe supervisor start/stop/reexec. Root `agent_entrypoint.py` is the executable/module shim.
- `local_agent/cli/diagnostics.py` owns diagnostics/status/task inspection. Root `agentctl.py` is the executable/module shim; the daemon must not depend on diagnostics.
- `local_agent/supervisor/resources.py` owns external machine/named-resource flock arbitration and inherited resource descriptors used by the parallel worker.
- `local_agent/supervisor/policy.py` owns shared polling/order/control policy.
- `local_agent/supervisor/scheduling.py` is the directly tested pure scheduling extraction target. Until `agent_parallel.py` is rewired in a focused change, parity tests must keep retry/backoff/due/max-worker behavior synchronized.
- `local_agent/supervisor/worker.py` owns parallel worker task admission/dispatch and hard-binding admission. Root `agent_parallel_worker.py` is an executable/module shim only.
- `local_agent/platform/macos_launchd.py` owns portable macOS LaunchAgent generation/lifecycle helpers. Machine-specific plist content must not be committed.
- Root compatibility/executable shims are not implementation owners. `tests/test_package_layout.py` enforces packaged module identity and a strict thin-source bound. New implementation belongs in `local_agent/`, and new code should import packaged owners directly rather than adding dependencies on legacy root aliases.
- Moving `agentd.py`, `agent_parallel.py` or `agent_multirepo.py` is not a cosmetic refactor: any change to their `__file__`-derived self-update, restart, worker or cwd paths requires explicit behavior-preserving tests before merge.

## Safety invariants

- One executable repository has one canonical opaque `agent_binding` UUID. Repository id, repository remote and binding are operational identity, not planner hints.
- Before claim/execution, both parallel and serial repository workers require local registry `agent_binding == .agent/binding.json agent_binding == task.agent_binding`.
- Missing repository binding is fail-closed `unbound`; invalid/mismatched control binding is fail-closed `binding_error`; missing/wrong task binding is a terminal pre-claim rejection and must execute no task command.
- Global operator `disabled` state takes precedence over repository binding admission so emergency stop remains authoritative during partial migrations or broken binding state.
- Chat Bridge conversations must not infer or switch repository identity from model context. A binding change is an explicit operator Rebind only.
- The `local-agent` catalog binding is bridge/operator-only (`execution_enabled: false`) and must never be used to queue project work.
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
- Keep Git staging path-exact; never use `git add -A` in publication logic.
- Preserve ignored build caches unless a task explicitly requests a clean rebuild.
- Never destroy a dirty disposable workspace without first creating a recoverable checkpoint outside the worktree.
- Treat repository control clones as daemon infrastructure. Queue normal work through the remote `agent-control` branch rather than hand-editing those clones.

## Production scheduling invariants

The bounded-parallel production path is `agent_parallel.py`:

- recommended production `max_workers` is `2`;
- default remains `1` and the hard cap remains `3`;
- `agent_multirepo.py` remains the known-safe serial fallback and preserves the same hard binding admission contract;
- serial and parallel supervisors share the same daemon lock and must never run simultaneously;
- every task must declare `resources` explicitly; missing, malformed, duplicated or non-canonical declarations are terminal task-contract errors, never silent fallbacks;
- `resources: []` means the task needs no exclusive external resource beyond its repository lease; builds, tests, lint and other repository-local software work may use it regardless of `memory_limit_mb`;
- named resources serialize only tasks sharing the same concrete external resource, for example `board:growbox-s3` or `board:zigbee-c6`;
- `resources: ["machine"]` is reserved for operations that truly require the whole host and must not be used merely because a task is a build, hardware test or has a large RSS limit;
- `memory_limit_mb` is a per-task watchdog bound and is independent from resource classification;
- every normal task holds the shared machine lock so a true `machine` task can drain and acquire global exclusivity;
- machine and named-resource descriptors are inherited into command descendants so locks survive worker death until the last holder exits;
- resource acquisition is non-blocking admission before claim/execution; contention leaves the immutable task pending and retries with bounded backoff instead of failing or disappearing;
- repository workers publish `waiting_resource` with the pending task/resource when admission is blocked;
- machine contention retains priority/drain fairness so full-host maintenance cannot starve;
- while workers are active, maintenance may only probe control state; global restart/status/self-update handling waits for a quiescent worker set and acquires all configured repository identities;
- after initial supervisor control service succeeds, degraded control probes retry promptly without blocking unrelated task admission; confirmed `PENDING` control drains immediately, while repeated control-repository lease contention enters a bounded drain after six consecutive deferrals so global control cannot starve;
- registry entries must not be removed or identity-mutated while workers may still be alive.

Repository isolation, hard agent binding and external-resource isolation are separate contracts. One repository still runs one task at a time, while independent hard-bound repositories may compile/test concurrently whenever their declared external resources do not conflict.

## Release and branch policy

- `main` is the production/runtime source of truth.
- Normal installed runtime must execute from `~/local-agent` on `main` so validated self-update and revision reporting work normally.
- Non-trivial runtime changes are prepared on isolated candidate branches/worktrees.
- Staging/candidate branches are validation infrastructure, not long-lived production branches.
- Require exact-candidate compile, Ruff, full unit/integration, Chat Bridge JS tests and macOS smoke before advancing `main`.
- Hard-binding releases additionally require negative missing/wrong-binding coverage on parallel and serial paths plus real E2E of active `cancel_task` and global `disable` before execution is left enabled.
- Advance `main` only after an explicit release decision and successful exact-candidate validation.
- Tag the released main commit with `vX.Y.Z` and keep `local_agent.version.RELEASE_VERSION` synchronized with that tag.
- After live verification from `main`, remove obsolete staging worktrees/branches instead of accumulating them.

## Downstream documentation synchronization

Planner-facing Local Agent behavior is a cross-repository contract. Any change that materially affects task fields, control-plane paths, status/result fields, execution model, agent binding, resource classification, concurrency, launchd deployment, self-update behavior, release flow or planner instructions must include a downstream documentation audit before release.

The currently registered downstream repositories are:

- `MichalMatu/esp32s3_LiteGraph` — update `LOCAL_AGENT_FLOW.md`, `LOCAL_AGENT_AUTOPILOT.md` when task construction/autonomy changes, and `AGENTS.md` when the contract is repeated there.
- `MichalMatu/growbox-ml-controller` — update root `AGENTS.md` on `main` and any active long-lived work branch that carries its own Local Agent bootstrap; currently `mvp/environment-controller` must stay synchronized.
- `MichalMatu/MatrixHub` — update root `AGENTS.md` on `main` and the active long-lived development branch when it differs; currently `develop` must stay synchronized.
- `MichalMatu/esp32_c6_zigbee` (repository id: `esp32-c6-zigbee`) — update root `AGENTS.md` on `main` when the Local Agent task/control/resource/status/planner contract changes.

Do not hard-code downstream release numbers unless a repository intentionally documents a historical baseline. Runtime compatibility instructions should prefer `.agent/status/daemon.json` plus canonical `MichalMatu/local-agent/main`.

The release audit is incomplete when these downstream instructions materially contradict the candidate runtime. Update downstream docs before moving `main` or explicitly document why no downstream change is required.

## Verification policy

Verification is impact-driven:

- run the narrowest test/build that can detect a realistic regression from the current diff;
- add broader coverage for shared/cross-cutting changes, uncertain dependency impact, explicit repository requirements or user requests;
- new binding/control/progress/watchdog/process-lifecycle behavior requires unit coverage;
- scheduler, isolation, provisioning or resource-arbitration changes require real temporary-Git integration coverage;
- repository lease/process-lifecycle changes require real SIGTERM/SIGKILL process tests;
- bounded parallel changes require real overlap and exclusivity evidence, not only mocks;
- hard binding must have positive and negative admission evidence on both the production parallel worker and serial fallback;
- package ownership moves require `tests/test_package_layout.py` plus the normal full suite.

Use `workflow_policy: "efficient-verification-v1"` for staged coding tasks that must make verification cost explicit. Use `work` for implementation, `focused` for affected regression/static checks and exactly one final `full` verification stage.

For repository-wide daemon verification, the executable source of truth is:

```bash
python scripts/verify.py
```

CI additionally runs branch-aware coverage, Python 3.14 compatibility and the macOS smoke suite. Do not recreate static compile/Ruff file lists in documentation or workflows; extend `scripts/verify.py` when verification scope changes.

Parallel scheduler releases additionally require real two-repository overlap, machine-exclusion, inherited-resource-lock, one-shot contention and macOS smoke coverage.

## Documentation

- Canonical workflow: `docs/OPERATIONS.md`.
- Current package/dependency map: `docs/ARCHITECTURE.md`.
- Autonomous ChatGPT planner/Chat Bridge loop: `docs/AUTONOMOUS_CHAT_LOOP.md`.
- Multi-repository architecture: `docs/MULTI_REPOSITORY.md`.
- Emergency controls: `docs/EMERGENCY_CONTROLS.md`.
- v4.11 parallel design/audit/live evidence: `docs/PARALLEL_EXECUTION_PLAN.md`.
- Established Mac/ESP32 setup: `docs/SESSION_BOOTSTRAP.md`.
- Current production invariants: `docs/GOLDEN_STANDARD.md`.
- Historical notes under `docs/history/` are non-canonical.

## Verification output policy

- Structured `steps` and `verify_steps` may declare `output_policy: "stream"` or `"summary"`.
- `summary` suppresses routine live command lines but preserves bounded raw output in terminal result evidence.
- Failed summary stages emit a bounded diagnostic tail; explicit progress markers remain visible and heartbeat, timeout, RSS and process cleanup behavior remains unchanged.
