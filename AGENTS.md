# Local Agent repository rules

This repository is execution infrastructure. Prefer deterministic behavior, bounded execution, explicit failure and recoverable state over clever recovery.

## Execution contract

- All machine-generated execution content is English-only: source, comments, identifiers, tests, documentation, prompts, task metadata, runtime logs, shell-visible status text and commit messages.
- Interactive ChatGPT conversation language is independent from that execution contract.
- Every newly authored Codex/agent prompt must restate the English-only execution requirement near the top.
- `agentd.py` owns the validated single-repository daemon implementation, durable claims/results, remote status/control and self-update.
- `agent_core.py` owns deterministic task execution and result publication.
- `agent_runtime.py` owns staged command lifecycle, watchdogs, progress and telemetry.
- `agent_process.py` owns shared shell spawning, bounded stdout handoff/capture and process-group termination primitives.
- `agent_repository.py` owns repository registry parsing and workspace identity.
- `agent_repo_worker.py` owns one short-lived, process-isolated repository polling/execution turn.
- `agent_multirepo.py` owns the multi-repository scheduler and the global execution-concurrency boundary.
- `agent_repo_admin.py` owns explicit repository workspace provisioning and validation.
- `agentctl.py` is diagnostics only; the daemon must not depend on it.

## Safety invariants

- Never automatically replay a task after daemon/process interruption.
- Never silently reuse a task id for a different payload within one repository.
- In multi-repository mode, task/result/claim identity is repository-scoped; identical task ids in different repositories must not collide.
- Malformed task JSON is terminal `invalid_task_file`, not a retry candidate.
- Keep command/no-output/RSS watchdogs and the whole-task admission budget intact unless a change explicitly replaces them with an equivalent or stronger mechanism.
- Command stdout transport and retained result capture must remain strictly bounded.
- Never terminate an already-running stage solely because the whole-task admission budget expired.
- Runtime execution must be passed explicitly into core task processing; do not mutate a global command runner to install production runtime behavior.
- Multi-repository scheduling must keep global execution concurrency at one unless a future design explicitly introduces machine-resource arbitration.
- Never mutate `agent_core.CONTROL`, `WORK`, `CHECKPOINTS` or equivalent repository globals in the long-lived multi-repository supervisor. Legacy path binding is allowed only inside a short-lived repository worker process.
- Repository control/work/checkpoint paths must be unique. A registry path collision is terminal configuration failure.
- A repository worker failure before task execution must not prevent the supervisor from polling other configured repositories.
- Repository workers must never execute global daemon restart/self-update directly. Those actions are supervisor-wide maintenance operations, not repository-local controls.
- Repository polling must never implicitly clone, overwrite or repair a checkout. Provisioning is an explicit administrative operation.
- Existing non-Git paths must never be overwritten by provisioning.
- All daemon self-updates must validate before restart and roll back on failure.
- Do not add a local coding LLM to the deterministic execution path.
- Keep Git staging path-exact; never use `git add -A` in publication logic.
- Preserve ignored build caches unless a task explicitly asks for a clean rebuild.
- Never destroy a dirty disposable workspace without first creating a recoverable checkpoint outside the worktree.
- Treat repository control clones as daemon infrastructure. Queue normal work through the remote `agent-control` branch rather than hand-editing those clones.

## Legacy semantics

`local-agent` is not feature-identical to DeterministicRunner:

- `expected_head` is not implemented; verify an expected Git SHA explicitly when source identity matters.
- Every declared command executes independently, including identical command strings.
- Cleanup intentionally preserves ignored caches.
- The established deployment is macOS/POSIX-specific and uses `launchd`.
- Without a multi-repository registry, the registry layer resolves to the established LiteGraph workspace layout.

## Verification policy

Verification is impact-driven:

- run the narrowest test/build that can detect a realistic regression from the current diff;
- add broader coverage only for shared/cross-cutting changes, uncertain dependency impact, an explicit repository requirement, or an explicit user request;
- previously green focused evidence remains valid while the covered code and relevant dependencies remain unchanged;
- after a focused fix, rerun only the affected gate unless the fix expands the impact surface;
- new control/progress/watchdog/process-lifecycle behavior requires unit coverage;
- multi-repository scheduler, isolation or provisioning changes require real temporary-Git integration coverage in addition to unit tests.

For daemon changes, before publication run:

```bash
python -m py_compile agentd.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_repo_admin.py agentctl.py
ruff check agentd.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_repo_admin.py agentctl.py tests
python -m unittest discover -q
```

For non-trivial daemon changes use an isolated `v*-staging` branch, require green GitHub CI on the exact staging SHA, then fast-forward `main` to that validated SHA. Never prepare a release by switching the live daemon checkout onto staging.

A multi-repository release additionally requires an isolated macOS two-repository smoke test on the exact candidate SHA and confirmation that the production daemon/worktree remains unchanged after the test.

## Documentation

Canonical workflow: `docs/OPERATIONS.md`.
Multi-repository architecture and administration: `docs/MULTI_REPOSITORY.md`.
Established Mac/ESP32 deployment: `docs/SESSION_BOOTSTRAP.md`.
Current invariants/audit state: `docs/GOLDEN_STANDARD.md`.
Historical design notes under `docs/history/` are non-canonical.
