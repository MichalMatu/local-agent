# Local Agent repository rules

This repository is execution infrastructure. Prefer deterministic behavior, bounded execution, explicit failure and recoverable state over clever recovery.

## Execution contract

- All machine-generated execution content is English-only: source, comments, identifiers, tests, documentation, prompts, task metadata, runtime logs, shell-visible status text and commit messages.
- Interactive ChatGPT conversation language is independent from that execution contract.
- `agentd.py` owns the validated daemon core, durable claims/results, remote status/control and self-update.
- `agent_core.py` owns deterministic task execution and result publication.
- `agent_runtime.py` owns staged command lifecycle, watchdogs, progress and telemetry.
- `agent_process.py` owns registered spawning, bounded stdout transport, process groups and inherited lease descriptors.
- `agent_repository.py` owns repository registry parsing and workspace identity.
- `agent_repo_worker.py` owns one short-lived process-isolated repository turn.
- `agent_parallel.py` owns the released bounded-parallel multi-repository scheduler.
- `agent_parallel_worker.py` owns task resource admission for the parallel scheduler.
- `agent_multirepo.py` remains the direct serial fallback with global concurrency one.
- `agent_repo_admin.py` owns explicit repository provisioning and validation.
- `agentctl.py` is diagnostics only; the daemon must not depend on it.

## Safety invariants

- Never automatically replay a task after daemon/process interruption.
- Never silently reuse a task id for a different payload within one repository.
- Task/result/claim identity is repository-scoped; identical task ids in different repositories must not collide.
- Malformed task JSON is terminal `invalid_task_file`, not a retry candidate.
- Keep command/no-output/RSS watchdogs and the whole-task admission budget intact unless a change explicitly replaces them with an equivalent or stronger mechanism.
- Command stdout transport and retained result capture must remain strictly bounded.
- Never terminate an already-running stage solely because the whole-task admission budget expired.
- Never mutate repository path globals in a long-lived supervisor. Legacy path binding is allowed only inside a short-lived repository worker process.
- Repository ids and remote identities are case-insensitively unique. Control/work/checkpoint paths must be disjoint after normalization, alias and ancestor/descendant checks.
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

The v4.11 production multi-repository path is `agent_parallel.py`:

- recommended production `max_workers` is `2`;
- default remains `1` and the hard cap remains `3`;
- `agent_multirepo.py` remains the known-safe serial fallback;
- serial and parallel supervisors share the same daemon lock and must never run simultaneously;
- missing, malformed or oversized `resources` means full `machine` exclusivity;
- `resources=[]` is an explicit software-only parallel declaration, never a generic default;
- named resources serialize tasks sharing that resource while unrelated resources may overlap;
- any non-machine task must have `memory_limit_mb` enabled and at or below 1024 MiB, otherwise it falls back to `machine` exclusivity;
- machine and named-resource descriptors are inherited into command descendants so locks survive worker death until the last holder exits;
- resource acquisition is non-blocking admission; a worker must never wait on a resource after selecting a task and before claiming it;
- machine contention enters priority/drain mode so full-machine work cannot starve behind a stream of shared tasks;
- while workers are active, maintenance may only probe control state; global restart/status/self-update handling waits for a quiescent worker set and acquires all configured repository identities;
- after initial supervisor control service succeeds, a `DEFERRED` control probe retries promptly without blocking unrelated task admission; only confirmed `PENDING` global control enters drain mode;
- registry entries must not be removed or identity-mutated while workers may still be alive.

A task is parallel-safe only when the planner knows it does not touch shared machine hardware or unsafe global tooling. Unknown, PlatformIO-heavy, USB, serial, flashing and hardware-sensitive work stays machine-exclusive unless an explicit resource contract proves otherwise.

## Release and branch policy

- `main` is the production/runtime source of truth.
- Normal installed runtime must execute from `~/local-agent` on `main` so validated self-update and revision reporting work normally.
- Non-trivial runtime changes are prepared on isolated `v*-staging` branches/worktrees.
- Staging branches are candidate-validation infrastructure, not long-lived production branches.
- Require exact-candidate compile, Ruff, full unit/integration and macOS smoke before advancing `main`.
- Advance `main` only by validated fast-forward after an explicit release decision.
- Tag the released main commit with `vX.Y.Z` and keep `agent_version.RELEASE_VERSION` synchronized with that tag.
- After live verification from `main`, remove obsolete staging worktrees/branches instead of accumulating them.

## Downstream documentation synchronization

Planner-facing Local Agent behavior is a cross-repository contract. Any change that materially affects task fields, control-plane paths, status/result fields, execution model, resource classification, concurrency, launchd deployment, self-update behavior, release flow or planner instructions must include a downstream documentation audit before release.

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
- new control/progress/watchdog/process-lifecycle behavior requires unit coverage;
- scheduler, isolation, provisioning or resource-arbitration changes require real temporary-Git integration coverage;
- repository lease/process-lifecycle changes require real SIGTERM/SIGKILL process tests;
- bounded parallel changes require real overlap and exclusivity evidence, not only mocks.

Use `workflow_policy: "efficient-verification-v1"` for staged coding tasks that must make verification cost explicit. Use `work` for implementation, `focused` for affected regression/static checks and exactly one final `full` verification stage.

For daemon changes, before publication run:

```bash
python -m py_compile agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_parallel.py agent_parallel_worker.py agent_repo_admin.py agent_storage.py agentctl.py agent_version.py
ruff check agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_parallel.py agent_parallel_worker.py agent_repo_admin.py agent_storage.py agentctl.py agent_version.py tests
python -m unittest discover -q
```

Parallel scheduler releases additionally require real two-repository overlap, machine-exclusion, inherited-resource-lock, one-shot contention and macOS smoke coverage.

## Documentation

- Canonical workflow: `docs/OPERATIONS.md`.
- Autonomous ChatGPT planner/Chat Bridge loop: `docs/AUTONOMOUS_CHAT_LOOP.md`.
- Multi-repository architecture: `docs/MULTI_REPOSITORY.md`.
- v4.11 parallel design/audit/live evidence: `docs/PARALLEL_EXECUTION_PLAN.md`.
- Established Mac/ESP32 setup: `docs/SESSION_BOOTSTRAP.md`.
- Current production invariants: `docs/GOLDEN_STANDARD.md`.
- Historical notes under `docs/history/` are non-canonical.
