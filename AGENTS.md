# Local Agent repository rules

This repository is execution infrastructure. Prefer deterministic behavior, bounded execution, explicit failure and recoverable state over clever recovery.

## Execution contract

- All machine-generated execution content is English-only: source, comments, identifiers, tests, documentation, prompts, task metadata, runtime logs, shell-visible status text and commit messages.
- Interactive ChatGPT conversation language is independent from that execution contract.
- Every newly authored Codex/agent prompt must restate the English-only execution requirement near the top.
- `agentd.py` owns queue orchestration, durable claims, remote status/control and self-update.
- `agent_core.py` owns deterministic task execution and result publication.
- `agent_runtime.py` owns staged command lifecycle, watchdogs, progress and telemetry.
- `agent_process.py` owns shared shell spawning, bounded stdout handoff/capture and process-group termination primitives.
- `agentctl.py` is diagnostics only; the daemon must not depend on it.

## Safety invariants

- Never automatically replay a task after daemon/process interruption.
- Never silently reuse a task id for a different payload.
- Malformed task JSON is terminal `invalid_task_file`, not a retry candidate.
- Keep command/no-output/RSS watchdogs and the whole-task admission budget intact unless a change explicitly replaces them with an equivalent or stronger mechanism.
- Command stdout transport and retained result capture must remain strictly bounded.
- Never terminate an already-running stage solely because the whole-task admission budget expired.
- Runtime execution must be passed explicitly into core task processing; do not mutate a global command runner to install production runtime behavior.
- All daemon self-updates must validate before restart and roll back on failure.
- Do not add a local coding LLM to the deterministic execution path.
- Keep Git staging path-exact; never use `git add -A` in publication logic.
- Preserve ignored build caches unless a task explicitly asks for a clean rebuild.
- Never destroy a dirty disposable workspace without first creating a recoverable checkpoint outside the worktree.
- Treat `~/agent-workspace/control` as daemon infrastructure. Queue normal work through the remote `agent-control` branch rather than hand-editing that clone.

## Legacy semantics

`local-agent` is not feature-identical to DeterministicRunner:

- `expected_head` is not implemented; verify an expected Git SHA explicitly when source identity matters.
- Identical command strings within one task may reuse the earlier result instead of executing again.
- Cleanup intentionally preserves ignored caches.
- The established deployment is macOS/POSIX-specific and uses `launchd`.

## Verification policy

Verification is impact-driven:

- run the narrowest test/build that can detect a realistic regression from the current diff;
- add broader coverage only for shared/cross-cutting changes, uncertain dependency impact, an explicit repository requirement, or an explicit user request;
- previously green focused evidence remains valid while the covered code and relevant dependencies remain unchanged;
- after a focused fix, rerun only the affected gate unless the fix expands the impact surface;
- new control/progress/watchdog/process-lifecycle behavior requires unit coverage.

For daemon changes, before publication run:

```bash
python -m py_compile agentd.py agent_core.py agent_runtime.py agent_process.py agentctl.py
ruff check agentd.py agent_core.py agent_runtime.py agent_process.py agentctl.py tests
python -m unittest discover -q
```

For non-trivial daemon changes use an isolated `v*-staging` branch, require green GitHub CI on the exact staging SHA, then fast-forward `main` to that validated SHA. Never prepare a release by switching the live daemon checkout onto staging.

## Documentation

Canonical workflow: `docs/OPERATIONS.md`.
Established Mac/ESP32 deployment: `docs/SESSION_BOOTSTRAP.md`.
Current invariants/audit state: `docs/GOLDEN_STANDARD.md`.
Historical design notes under `docs/history/` are non-canonical.
