# Local Agent repository rules

This repository is execution infrastructure. Prefer deterministic behavior, bounded execution, explicit failure and recoverable state over clever recovery.

## Execution contract

- All machine-generated execution content is English-only: source, comments, identifiers, tests, documentation, prompts, task metadata, runtime logs, shell-visible status text and commit messages.
- Interactive ChatGPT conversation language is independent from that execution contract.
- Every newly authored Codex/agent prompt must restate the English-only execution requirement near the top.
- `agentd.py` owns the validated daemon core, durable claims/results, remote status/control and self-update.
- `agent_core.py` owns deterministic task execution and result publication.
- `agent_runtime.py` owns staged command lifecycle, watchdogs, progress and telemetry.
- `agent_process.py` owns registered spawning, bounded stdout transport, process groups and inherited lease descriptors.
- `agent_repository.py` owns repository registry parsing and workspace identity.
- `agent_repo_worker.py` owns one short-lived process-isolated repository turn.
- `agent_multirepo.py` owns the released serial multi-repository scheduler and remains the direct fallback.
- `agent_parallel.py` owns the opt-in bounded parallel staging scheduler.
- `agent_parallel_worker.py` owns task resource admission for the parallel scheduler.
- `agent_repo_admin.py` owns explicit repository workspace provisioning and validation.
- `agentctl.py` is diagnostics only; the daemon must not depend on it.

## Safety invariants

- Never automatically replay a task after daemon/process interruption.
- Never silently reuse a task id for a different payload within one repository.
- Task/result/claim identity is repository-scoped; identical task ids in different repositories must not collide.
- Malformed task JSON is terminal `invalid_task_file`, not a retry candidate.
- Keep command/no-output/RSS watchdogs and the whole-task admission budget intact unless a change explicitly replaces them with an equivalent or stronger mechanism.
- Command stdout transport and retained result capture must remain strictly bounded.
- Never terminate an already-running stage solely because the whole-task admission budget expired.
- Runtime execution must be passed explicitly into core task processing; do not mutate a global command runner to install production runtime behavior.
- Never mutate repository path globals in a long-lived supervisor. Legacy path binding is allowed only inside a short-lived repository worker process.
- Repository ids and remote identities are case-insensitively unique. Control/work/checkpoint paths must be disjoint after normalization, alias and ancestor/descendant checks.
- A repository turn holds OS execution leases for its id, remote and every workspace path. Those descriptors must survive supervisor and worker failure through every spawned descendant.
- Stale-claim recovery must not inspect or mutate a repository while an earlier process still owns any matching execution lease.
- A worker must reject dispatch when its exact repository configuration changed after the supervisor selected it.
- Every daemon, supervisor and worker subprocess must use the shared registered spawn path so termination cannot race an unregistered child.
- Repository polling never implicitly clones, overwrites or repairs a checkout. Provisioning is explicit.
- Existing non-Git paths must never be overwritten by provisioning.
- Repository workers must never execute global daemon restart/self-update directly.
- All daemon self-updates must validate before restart and roll back on validation failure.
- Keep Git staging path-exact; never use `git add -A` in publication logic.
- Preserve ignored build caches unless a task explicitly requests a clean rebuild.
- Never destroy a dirty disposable workspace without first creating a recoverable checkpoint outside the worktree.
- Treat repository control clones as daemon infrastructure. Queue normal work through the remote `agent-control` branch rather than hand-editing those clones.

## Serial and parallel scheduling invariants

The released fallback remains `agent_multirepo.py` with global execution concurrency exactly one.

The v4.11 staging path is explicitly opt-in through `agent_parallel.py`:

- default `max_workers` is `1`;
- staging hard cap is `3`;
- first validated/live deployment uses `max_workers=2`;
- the serial and parallel supervisors share the same daemon lock and must never run simultaneously;
- missing, malformed or oversized `resources` declarations are conservative and mean `resources=["machine"]`;
- `resources=[]` is software-only parallel admission, not a generic default;
- named resources serialize tasks sharing the same resource while allowing unrelated named resources to overlap;
- any parallel/named-resource task must keep `memory_limit_mb` enabled and at or below 1024 MiB, otherwise it falls back to `machine` exclusivity;
- machine and named resource descriptors are inherited into command descendants so locks survive worker death until the last holder exits;
- resource acquisition is non-blocking admission. A worker must never wait for a resource after selecting a task and before claiming it;
- machine contention enters priority/drain mode so a full-machine task cannot starve behind a stream of shared tasks;
- while workers are active, supervisor maintenance polling may only probe control state. Global restart/status/self-update handling must wait for a quiescent worker set and acquire every configured repository execution identity;
- registry entries must not be removed or identity-mutated while staging workers may still be alive.

A task is parallel-safe only when the planner knows it does not touch shared machine hardware or unsafe global tooling. Unknown, USB, serial, flashing and other hardware-sensitive work remains machine-exclusive unless a future explicit arbitration contract says otherwise.

## Verification policy

Verification is impact-driven:

- run the narrowest test/build that can detect a realistic regression from the current diff;
- add broader coverage only for shared/cross-cutting changes, uncertain dependency impact, an explicit repository requirement, or an explicit user request;
- new control/progress/watchdog/process-lifecycle behavior requires unit coverage;
- scheduler, isolation, provisioning or resource-arbitration changes require real temporary-Git integration coverage in addition to unit tests;
- repository lease or process-lifecycle changes require real SIGTERM/SIGKILL process tests;
- bounded parallel changes require real overlap and exclusivity evidence, not only mocks.

Use `workflow_policy: "efficient-verification-v1"` for staged coding tasks that must make verification cost explicit. Every `steps` and `verify_steps` item declares `verification_level`; use `work` for implementation, `focused` for affected regression/static checks and exactly one final `full` verification stage.

For daemon changes, before publication run:

```bash
python -m py_compile agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_parallel.py agent_parallel_worker.py agent_repo_admin.py agent_storage.py agentctl.py agent_version.py
ruff check agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_parallel.py agent_parallel_worker.py agent_repo_admin.py agent_storage.py agentctl.py agent_version.py tests
python -m unittest discover -q
```

For non-trivial daemon changes use an isolated `v*-staging` branch and require green GitHub CI on the exact candidate SHA. Never prepare a release by switching the known-good `~/local-agent` checkout away from `main`.

Parallel scheduler releases additionally require real two-repository overlap, machine-exclusion, inherited-resource-lock, one-shot contention and macOS smoke coverage. `main` advances only after an explicit release decision.

## Documentation

- Canonical workflow: `docs/OPERATIONS.md`.
- Autonomous ChatGPT planner/Chat Bridge loop: `docs/AUTONOMOUS_CHAT_LOOP.md`.
- Multi-repository architecture and administration: `docs/MULTI_REPOSITORY.md`.
- Parallel staging contract and live evidence: `docs/PARALLEL_EXECUTION_PLAN.md`.
- Established Mac/ESP32 setup: `docs/SESSION_BOOTSTRAP.md`.
- Current invariants/audit state: `docs/GOLDEN_STANDARD.md`.
- Historical design notes under `docs/history/` are non-canonical.
