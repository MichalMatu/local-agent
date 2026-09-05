# Local Agent Operations

This is the canonical operational workflow for `MichalMatu/local-agent`.

## Production topology

The production/runtime source is `~/local-agent` on `main`. Releases are tagged `vX.Y.Z`. Temporary `v*-staging` branches/worktrees are candidate-development infrastructure only.

The recommended bounded-parallel supervisor is:

```bash
python agent_parallel.py --registry "$HOME/Library/Application Support/local-agent/repositories.json" --max-workers 2
```

`agent_multirepo.py` remains the direct serial fallback with global concurrency one. In 4.15 both execution paths enforce the same hard agent-binding admission contract. The two supervisors use the same daemon lock and must never run simultaneously.

## Hard agent-binding contract

Local Agent 4.15 and Chat Bridge 0.4 make repository routing an explicit identity, not a planner hint.

Every executable repository has one canonical lowercase UUID `agent_binding`. The canonical catalog lives at:

```text
config/agent_bindings.json
```

The same UUID must exist in all three executor-side locations:

```text
~/Library/Application Support/local-agent/repositories.json
    repositories[].agent_binding

<repository control checkout>/.agent/binding.json
    agent_binding + repository_id + repository

<agent-control>/.agent/tasks/<task-id>.json
    agent_binding
```

Before claim/execution the worker requires:

```text
registry binding == control binding == task binding
```

The parallel worker and serial fallback both enforce this. Failure is fail-closed:

- registry binding absent -> repository status `unbound`, no task admission;
- `.agent/binding.json` missing/invalid/mismatched -> `binding_error`, no task admission;
- task binding absent -> terminal `agent_binding_missing`, before claim/commands;
- task binding mismatched -> terminal `agent_binding_mismatch`, before claim/commands.

The global operator `disabled` marker is checked before repository binding admission. Emergency stop therefore remains authoritative even during a partial/broken migration.

Repository binding is operational identity. Do not rotate a UUID to repair a task or switch a chat. A Chat Bridge conversation can change repository only through explicit **Rebind**; executor configuration changes require an intentional disabled migration.

The `local-agent` catalog entry is `execution_enabled: false`. It is reserved for bridge/operator infrastructure conversations and must not be used to queue project tasks.

## Binding migration while disabled

A 4.15 upgrade must be fail-closed:

```bash
cd ~/local-agent
.venv/bin/python -m local_agent.operator.local disable --reason binding-migration
.venv/bin/python -m local_agent.operator.local status
.venv/bin/python -m local_agent.operator.local migrate-bindings
```

`migrate-bindings` refuses to run unless Local Agent is disabled. It applies the canonical catalog to the local repository registry and refuses an existing UUID that disagrees with the catalog.

Before enabling, verify every enabled repository has a matching committed `.agent/binding.json` on its `agent-control` branch. The file format is:

```json
{
  "version": 1,
  "repository_id": "matrixhub",
  "repository": "MichalMatu/MatrixHub",
  "agent_binding": "033327ab-700d-43b4-9b3b-caff1acaa2c7"
}
```

Do not enable execution while any repository reports `unbound` or `binding_error`.

## Chat Bridge 0.4 rollout

Bridge state schema 3 stores immutable conversation binding fields:

```text
repositoryId
repository
agentBinding
bindingRevision
bindingSetAt
```

Legacy/unbound conversations migrate disabled with `binding_required`; they receive no alarm. Normal conversation edits cannot alter binding fields. Explicit Rebind is the only supported route change and forces a new bootstrap.

Remote runtime schema 3 publishes the canonical agent catalog. Production runtime is served from branch `chat-bridge-state`, file `chat_bridge/runtime.json`. Rollout order matters:

1. keep Local Agent globally disabled;
2. release/fast-forward Local Agent 4.15 code and validate CI;
3. update/reload Chat Bridge 0.4;
4. publish runtime schema 3 with the matching catalog;
5. verify migrated chats are fail-closed and intended chats have exact bindings;
6. run binding-negative E2E plus emergency-control E2E;
7. enable Local Agent only after those checks are green.

Publishing schema 3 before an old bridge is replaced is not a reason to enable execution. The kill switch remains the safety boundary during rollout.

## Control data

Each registered repository uses its own `agent-control` branch:

```text
.agent/binding.json
.agent/tasks/<task-id>.json
.agent/runs/<task-id>.json
.agent/results/<task-id>.json
.agent/status/daemon.json
.agent/daemon/control.json
.agent/daemon/acks/*.json
```

Task IDs/payloads are immutable within a repository. Interrupted claimed work is never silently replayed. Terminal results are durably spooled before publication; publication recovery may republish but may not re-execute commands.

Control synchronization keeps history shallow and explicitly fetches the control branch into `refs/remotes/origin/agent-control`. ACK verification therefore remains grounded in a fetched remote-tracking tree instead of a possibly unpushed local commit. This is required for reliable active `cancel_task` and other control ACK checks.

## Parallel resource contract

Every task must declare `resources` explicitly. Missing, malformed, duplicated, oversized or non-canonical declarations are terminal contract errors; there is no fallback to `machine`.

Repository-local work uses:

```json
{"resources": [], "memory_limit_mb": 2048}
```

Concrete exclusive resources use stable names, for example:

```json
{"resources": ["board:growbox-s3"]}
{"resources": ["board:zigbee-c6"]}
```

Full-host exclusivity is explicit:

```json
{"resources": ["machine"]}
```

`memory_limit_mb` remains an independent RSS watchdog and never implies machine exclusivity.

Resource acquisition is non-blocking before claim. Contention leaves the immutable task pending, reports `waiting_resource`, and retries with bounded backoff. Contention is WAIT, not task failure.

## Development workflow

1. Read `AGENTS.md`, this file and target-repository planner instructions.
2. Establish the exact repository/binding identity before queueing anything.
3. Inspect `.agent/status/daemon.json` and exact run/result evidence for that repository.
4. Confirm the intended `work_branch` when it differs from the default.
5. Prepare the smallest deterministic change.
6. Classify resources conservatively.
7. Queue one new unique task containing the exact `agent_binding` and explicit `resources`.
8. For Chat Bridge work, perform one early liveness check around 30 seconds.
9. Follow the same digest/attempt until terminal evidence exists.
10. Diagnose exact output; never infer success from submission.
11. Run focused verification first and one final broad gate when warranted.
12. Publish source according to the target repository Git policy.
13. Treat source publication and hardware flashing/runtime verification as separate gates.

For substantial staged work, prefer `workflow_policy: "efficient-verification-v1"`: `work` stages for implementation, `focused` stages for affected verification and exactly one final `full` verification stage.

For Local Agent itself, use the centralized repository verifier instead of maintaining a second file list:

```bash
python scripts/verify.py
python scripts/verify.py --only tests
python scripts/verify.py --profile macos-smoke
```

An autonomous conversation follows one active task at a time for its own goal. Independent repositories/conversations may overlap when executor resource admission permits it.

## Multi-repository administration

Registry:

```text
~/Library/Application Support/local-agent/repositories.json
```

Commands:

```bash
python -m local_agent.repository.admin list
python -m local_agent.repository.admin validate
python -m local_agent.repository.admin provision --repository-id <id>
python -m local_agent.operator.local migrate-bindings
```

Provisioning is explicit and never a poll-loop side effect. Repository ids/remotes/bindings and normalized control/work/checkpoint paths must remain disjoint and stable.

The first enabled registry entry is the supervisor control repository in registry v1. Reordering entries therefore changes the global restart/self-update/status control source; treat order as operational identity.

Do not remove or identity-mutate an active registry entry while workers/descendants may still be alive.

## Emergency controls

Local operator commands are in `local_agent.operator.local` and `docs/EMERGENCY_CONTROLS.md`. The global marker blocks admission independently of GitHub/control-branch health.

Repository controls include `cancel_task`, `disable` and status handling. Active-task control watching periodically synchronizes the target repository control branch. An active cancel is valid only when the fetched control request targets the exact active task and the control id is not already remotely acknowledged.

`disable` is global safety state, not merely a display status. When disabled, workers stop task admission even if task/binding data is otherwise valid.

Repository workers never execute supervisor-wide restart/self-update directly. While workers are active, the parallel supervisor probes global control and drains safely before global maintenance.

## Runtime bounds

Canonical defaults:

- command timeout 900 s, max 7200 s;
- no-output timeout 300 s, max 3600 s;
- whole-task budget 1800 s, max 21600 s;
- finalization reserve 60 s;
- normal RSS limit 4096 MiB, configurable max 16384 MiB.

Command stdout capture is bounded. Runtime limits are loaded at daemon startup.

## macOS deployment

LaunchAgent definitions are generated from the current checkout and user home. The repository does not track machine-specific plist files with hard-coded `/Users/<name>/...` paths. The full workflow is documented in [`deploy/macos/README.md`](../deploy/macos/README.md).

Inspect the generated definition without changing the machine:

```bash
cd ~/local-agent
.venv/bin/python scripts/macos_launchd.py render
```

Write/update `~/Library/LaunchAgents/com.michal.local-agent.plist` without touching the currently running service:

```bash
.venv/bin/python scripts/macos_launchd.py install \
  --mode parallel \
  --max-workers 2
```

Inspect the loaded service:

```bash
.venv/bin/python scripts/macos_launchd.py status
```

Only when it is safe to interrupt active work, explicitly regenerate and restart the LaunchAgent:

```bash
.venv/bin/python scripts/macos_launchd.py restart \
  --mode parallel \
  --max-workers 2
```

`install` and `restart` are intentionally separate operations. A configuration write must never silently interrupt an active Local Agent task.

All modes use the same `com.michal.local-agent` label and are replacement configurations, never additional concurrent services. `parallel` is the production default, `multirepo` is the serial fallback and `single` is the direct daemon mode.

Cold-start rollout should begin disabled. Verify:

- launchd runs only the guarded entrypoint while disabled;
- `python -m local_agent.operator.local status` reports disabled;
- daemon state is `disabled`;
- no repository workers/tasks start;
- a queued probe remains unclaimed while disabled.

Only after binding/bridge/E2E gates are complete should `python -m local_agent.operator.local enable` remove the marker.

Rollback to `agent_multirepo.py` does not weaken hard binding in 4.15: the serial repository worker enforces the same registry/control/task equality. Do not roll back to a pre-4.15 binary while bound task queues are considered trusted.

## Release flow

### Package-layout transition from v4.17

The v4.17 updater's in-memory validation command names root aliases removed in v4.18. It correctly rejects the new layout. Perform this one-time transition through the operator: wait for idle, persist local disable with the installed `agent_operator.py disable`, stop the LaunchAgent, fast-forward the production checkout to the validated release, and restart using `scripts/macos_launchd.py restart --mode parallel --max-workers 2`. Verify disabled startup and live cancellation/disable E2E before leaving execution enabled. Keep registry, claims, result spool, workspaces and checkpoints intact.

### Interrupted self-update recovery

Updates record original and candidate revisions in `~/Library/Application Support/local-agent/installation-pending.json` before changing the checkout. The installation lock prevents the guard from interrupting validation. Failed validation rolls back and clears the journal; process interruption leaves it durable. The guard persists `disabled` with reason `interrupted_self_update`, and supervisor startup and local enable refuse an unfinished installation.

Recovery is explicit: stop the service while disabled, inspect and preserve the journal and any unexpected checkout changes, restore its recorded original revision (or complete full verification of the installed candidate), and only then remove the journal. Restart disabled and inspect the installed revision/status before explicit local enable. Never delete the journal merely to bypass validation. A runtime reset does not clear installation state.

Remote emergency polling remains active during an installation transaction. Local enable never clears an incomplete transaction.

### Candidate gates

For non-trivial runtime changes:

1. use an isolated candidate branch/worktree based on current `main`;
2. implement and run focused verification;
3. require compile, Ruff, full unittest/integration and macOS smoke on the exact candidate SHA;
4. review `main...candidate` and verify no unrelated/fallback-breaking changes;
5. audit planner-facing Local Agent docs in every registered downstream repository;
6. advance `main` only after the exact candidate is green;
7. tag released `main` `vX.Y.Z` matching `local_agent.version.RELEASE_VERSION`;
8. switch production to `~/local-agent` on released `main` and verify live status/result evidence;
9. remove obsolete staging branches/worktrees after release is established.

For 4.15, release verification additionally requires missing/wrong binding rejection on both parallel and serial execution paths, control-binding mismatch admission failure, Chat Bridge unbound/rebind tests, active `cancel_task`, and global `disable` E2E.

## Downstream documentation gate

Current execution targets are LiteGraph, Growbox ML Controller, MatrixHub and Tracker. ESP32-C6 Zigbee (`esp32-c6-zigbee`) is an archival disabled entry; active C6 development belongs to LiteGraph and a different Bridge binding requires explicit Rebind. Changes to task schema, planner flow, status/control or execution model require a downstream docs audit before release. See `AGENTS.md` for exact files/branches.

Downstream task examples must include `agent_binding` for executable Chat Bridge/Local Agent work and must not instruct a conversation to select/switch repositories from model context.

## Source of truth

1. exact Local Agent terminal command/result output;
2. target repository source/tests;
3. remote run/result/status/control evidence;
4. planner analysis.

## Verification and log discipline

Use focused regression during iteration, then one bounded full suite near the end. Long/noisy structured stages may use `output_policy: "summary"`; bounded raw evidence remains in terminal results.

Unexpected worker exits back off 2-300 s and reset after normal outcomes. Deferred global-control work backs off 2-15 s. Repeated control lease contention enters a bounded drain after six consecutive deferrals.

The production supervisor bounds `~/Library/Logs/local-agent.log` and `local-agent-error.log`. Routine successful internal Git housekeeping is quiet by default; actionable control failures, timeouts, nonzero internal commands, task lifecycle and other degraded states remain logged. Set `LOCAL_AGENT_VERBOSE_LOGS=1` only for temporary low-level diagnostics.
