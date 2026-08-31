# Local Agent Operations

This file is the canonical operational workflow for `MichalMatu/local-agent`. Multi-repository architecture lives in `MULTI_REPOSITORY.md`; bounded parallel staging details and live evidence live in `PARALLEL_EXECUTION_PLAN.md`.

## Roles and deployment tracks

The planner chooses exact changes and commands. The daemon executes deterministic tasks, records real output and publishes machine-readable evidence. It does not invent fixes.

The stable rollback track remains:

- daemon repository: `MichalMatu/local-agent`;
- source checkout: `~/local-agent` on `main`;
- scheduler: `agent_multirepo.py`;
- global task concurrency: exactly one.

The validated v4.11 staging track is separate:

- detached worktree: `~/local-agent-v4.11-parallel-staging`;
- runtime code candidate validated on macOS: `084e81b792cd01a261a0f0ee1a2a9b46b9964168`;
- scheduler: `agent_parallel.py`;
- current live staging setting: `--max-workers 2`;
- shared daemon lock: the serial and parallel supervisors cannot run simultaneously;
- launchd label remains `com.michal.local-agent`;
- serial plist backup: `~/Library/LaunchAgents/com.michal.local-agent.serial-backup.plist`.

Documentation-only commits may advance the staging branch after the validated runtime SHA. The running detached staging worktree must not be silently moved to a newer SHA; runtime changes require their own exact-SHA CI and smoke validation.

## Autonomous ChatGPT planner loop

The optional Chrome Chat Bridge may wake one selected ChatGPT conversation so the planner can inspect fresh Git-backed status/result evidence and decide whether to queue another task. The bridge does not plan, inspect code or execute commands. ChatGPT remains the planner and `local-agent` remains the deterministic executor.

The complete bridge contract is `AUTONOMOUS_CHAT_LOOP.md`. Keep one active task per repository conversation: do not queue another task for a repository while that repository reports an active task. Multiple repositories may have active tasks concurrently only when the parallel resource contract permits it.

## Control data and replay safety

Each repository `agent-control` branch stores queued tasks, live runs, terminal results, repository status and durable control acknowledgements under `.agent/`.

Task ids and payloads are immutable within one repository. Claimed or interrupted work is never replayed automatically. Final results are durably spooled before remote publication. Publication may retry; execution may not.

Task/result/claim identity is repository-scoped. Stale-claim recovery runs only while the worker owns inherited OS leases for the configured repository id, remote and workspace identities. If an earlier worker or descendant is still alive after a crash, a restarted supervisor defers that repository instead of recovering or replaying it.

## Runtime limits

Canonical defaults remain:

- command timeout: 900 seconds;
- maximum command/stage timeout: 7200 seconds;
- no-output timeout: 300 seconds;
- maximum no-output timeout: 3600 seconds;
- whole-task admission budget: 1800 seconds, maximum 21600 seconds;
- finalization reserve: 60 seconds;
- normal process-group RSS limit: 4096 MiB;
- maximum configurable RSS limit: 16384 MiB.

The parallel staging admission rule is stricter: a task may run without machine exclusivity only when `memory_limit_mb` is enabled and no greater than 1024 MiB. A disabled, omitted/default 4096 MiB or larger limit falls back to `machine` exclusivity.

Command output transport and retained result capture remain bounded. Runtime timeout configuration is read at daemon startup; restart the daemon after changing `LOCAL_AGENT_*` timeout settings.

## Task resource contract

Legacy and unknown tasks remain safe by default. If `resources` is omitted, malformed or oversized, the parallel worker treats the task as:

```json
{
  "resources": ["machine"]
}
```

That task runs exclusively against every other local-agent task.

Clearly software-only work may opt into overlap:

```json
{
  "resources": [],
  "memory_limit_mb": 512
}
```

Named resources may be used for explicit arbitration:

```json
{
  "resources": ["platformio"],
  "memory_limit_mb": 1024
}
```

Tasks sharing a named resource serialize on that resource. Different named resources may overlap. `"machine"` always means full exclusivity.

Do not mark a task software-only unless the planner knows it will not use shared machine hardware or unsafe global tooling. USB, serial, flashing and uncertain hardware work should omit `resources` and stay machine-exclusive during staging.

## Multi-repository administration

Registry location:

```text
~/Library/Application Support/local-agent/repositories.json
```

Validate after every registry edit:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
```

Provisioning is explicit:

```bash
python agent_repo_admin.py provision --repository-id <id>
```

Polling never implicitly clones, repairs or overwrites a checkout. Repository ids and remote identities must be unique case-insensitively; normalized control/work/checkpoint paths must be disjoint.

Do not remove or identity-mutate a configured repository while a staging worker or descendant may still be alive. The all-current-repositories global-control lease cannot protect a repository that has been removed from the registry entirely.

## Parallel supervisor maintenance

Normal maintenance polling must not destroy useful parallelism. While workers are active, `agent_parallel.py` only probes control state. A real unacknowledged global control request stops admission of new workers, lets current workers finish and then acquires every configured repository execution identity before restart/status/self-update handling.

Ordinary self-update waits for a natural idle window. The detached staging checkout is intentionally not on `main`, so the expected log is:

```text
self-update skipped: checkout is not on main
```

This is not an error. The staging runtime is deliberately pinned to a validated SHA.

Silent terminal Git failures are hardened: if Git produces no textual output, the staging code synthesizes a bounded diagnostic containing exit code and available timeout/background-leak/failure metadata instead of logging an empty `self-update fetch failed:` line.

## Live staging validation on 2026-08-31

The exact runtime candidate `084e81b792cd01a261a0f0ee1a2a9b46b9964168` passed GitHub CI on Linux and macOS before live use.

The manual macOS smoke then proved both sides of the resource contract with real queued tasks:

1. two software-only tasks in different repositories, each using `resources: []` and `memory_limit_mb: 512`, overlapped for approximately 17.5 seconds and both finished `done` with clean worktrees and no process leaks;
2. a task with no `resources` field ran machine-exclusive, and a software-only task in another repository started only after the exclusive task completed, producing zero overlap.

After Ctrl-C, no `agent_multirepo.py`, `agent_repo_worker.py`, `agent_parallel.py` or `agent_parallel_worker.py` processes remained. The staging LaunchAgent was then activated with `max_workers=2`, and local status reported `execution_model=parallel_repository_supervisor_staging`, the expected runtime SHA and an empty active repository set.

## LaunchAgent operation

Current staging LaunchAgent uses the existing label and plist path:

```text
~/Library/LaunchAgents/com.michal.local-agent.plist
```

It launches:

```text
/Users/michal/local-agent/.venv/bin/python
/Users/michal/local-agent-v4.11-parallel-staging/agent_parallel.py
--registry /Users/michal/Library/Application Support/local-agent/repositories.json
--max-workers 2
```

Logs:

```text
~/Library/Logs/local-agent-parallel-staging.log
~/Library/Logs/local-agent-parallel-staging-error.log
```

Useful checks:

```bash
launchctl print "gui/$(id -u)/com.michal.local-agent"
pgrep -af 'agent_multirepo.py|agent_repo_worker.py|agent_parallel.py|agent_parallel_worker.py' || true
cat "$HOME/Library/Application Support/local-agent/status.json"
tail -n 100 "$HOME/Library/Logs/local-agent-parallel-staging.log"
```

## Rollback

Rollback does not require repository migration or state conversion:

```bash
launchctl bootout "gui/$(id -u)/com.michal.local-agent" 2>/dev/null || true
cp -p "$HOME/Library/LaunchAgents/com.michal.local-agent.serial-backup.plist" \
  "$HOME/Library/LaunchAgents/com.michal.local-agent.plist"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/com.michal.local-agent.plist"
launchctl kickstart -k "gui/$(id -u)/com.michal.local-agent"
```

Then confirm the startup log reports the serial `agent_multirepo.py` supervisor and run one real queued task before considering rollback complete.

## Release flow

Non-trivial daemon changes are prepared on an isolated `v*-staging` branch. Require explicit compile, pinned Ruff, full unittest discovery, temporary-Git integration, real process/lease tests and green GitHub CI on the exact candidate SHA.

Parallel scheduler changes additionally require real overlap, machine-exclusion, contention/retry, inherited resource-lock lifetime and isolated macOS smoke evidence. Do not fast-forward `main` merely because staging is working live; merging remains a separate explicit release decision.

## Source of truth

1. real local-agent command/result output;
2. target source and tests;
3. remote run/status evidence;
4. analysis and documentation.
