# Local Agent Operations

This is the canonical operational workflow for `MichalMatu/local-agent`.

## Production topology

The production/runtime source is `~/local-agent` on `main`. Releases are tagged `vX.Y.Z`. Temporary candidate branches/worktrees are candidate-development infrastructure only.

The bounded-parallel production supervisor is:

```bash
python agent_parallel.py --registry "$HOME/Library/Application Support/local-agent/repositories.json" --max-workers 4
```

`agent_multirepo.py` remains the direct serial fallback with global concurrency one. Both execution paths enforce the same hard agent-binding admission contract. The two supervisors use the same daemon lock and must never run simultaneously.

The immutable known-working pre-BUG-002-fix baseline is:

```text
v4.18.13
= a32e54858c3bcb9687334b3232b71ae6ff130208
= rollback/v4.18.13-known-working
```

The current release candidate is v4.18.14. It is not production until explicitly advanced to `main`. See [`PRODUCTION_BASELINE_V4.18.13.md`](PRODUCTION_BASELINE_V4.18.13.md) before changing scheduler/control admission behavior.

## Hard agent-binding contract

Repository routing is an explicit identity, not a planner hint.

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

A binding migration must be fail-closed:

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

## Chat Bridge schema-3 rollout

The current Bridge state stores immutable conversation binding fields:

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
2. release/fast-forward Local Agent code and validate exact-candidate CI;
3. update/reload the matching Chat Bridge when the bridge contract changed;
4. publish runtime schema 3 with the matching catalog when catalog/runtime data changed;
5. verify migrated chats are fail-closed and intended chats have exact bindings;
6. run binding-negative E2E plus emergency-control E2E when those boundaries changed;
7. enable Local Agent only after required checks are green.

Publishing a new bridge runtime before an old bridge is replaced is not a reason to enable execution. The kill switch remains the safety boundary during rollout. Detailed current planner/Bridge semantics live in [`AUTONOMOUS_CHAT_LOOP.md`](AUTONOMOUS_CHAT_LOOP.md).

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

The currently registered project repositories use:

```json
{"resources": [], "memory_limit_mb": 2048}
```

for executable project work, including project-dedicated hardware operations. The task itself discovers and verifies the intended device/port before interacting with hardware. Repository execution leases already serialize tasks inside one repository.

The generic runtime still supports named resources for genuinely shared external resources, for example:

```json
{"resources": ["shared:example-device"]}
```

Full-host exclusivity is explicit:

```json
{"resources": ["machine"]}
```

`memory_limit_mb` remains an independent per-task RSS watchdog and never implies machine exclusivity. The supervisor does not sum requested memory limits or perform aggregate host-RAM admission.

Resource acquisition is non-blocking before claim. Contention leaves the immutable task pending, reports `waiting_resource`, and retries with bounded backoff. Contention is WAIT, not task failure.

## Development workflow

1. Read `AGENTS.md`, this file and target-repository planner instructions.
2. Establish the exact repository/binding identity before queueing anything.
3. Inspect `.agent/status/daemon.json` and exact run/result evidence for that repository.
4. Confirm the intended `work_branch` when it differs from the default.
5. Prepare the smallest deterministic change.
6. Classify resources explicitly; current registered project repositories use `resources: []` and detect/verify devices inside task commands.
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

The first enabled registry entry is the supervisor control repository in registry v1. Reordering entries therefore changes the global restart/self-update/status control source. v4.18.14 clears stale retry/lease-busy/pause state and invalidates the old poll clock when that identity changes.

Do not remove or identity-mutate an active registry entry while workers/descendants may still be alive.

## Emergency controls

Local operator commands are in `local_agent.operator.local` and [`EMERGENCY_CONTROLS.md`](EMERGENCY_CONTROLS.md). The global persistent disable marker and central `operator-control` branch remain independent of project control-branch health.

Repository controls include `cancel_task`, `disable` and status handling. Active-task control watching periodically synchronizes the target repository control branch. An active cancel is valid only when the fetched control request targets the exact active task and the control id is not already remotely acknowledged.

`disable` is global safety state, not merely a display status. When disabled, workers stop task admission even if task/binding data is otherwise valid.

Repository workers never execute supervisor-wide restart/self-update directly. While workers are active, the parallel supervisor probes global control and drains safely before confirmed global maintenance.

### v4.18.14 control-probe admission policy

The frozen v4.18.13 scheduler has confirmed BUG-002: a long task in the designated control repository legitimately owns its repository lease, so the periodic global-control probe returns `LEASE_BUSY`. Repeated expected ownership could trigger a global admission drain and block unrelated repositories even with `resources: []` and free worker capacity.

v4.18.14 separates retry evidence from the lease-busy starvation streak:

- each deferred probe participates in bounded 2-15 second retry/backoff;
- only true **consecutive `LEASE_BUSY`** outcomes count toward the six-attempt lease-ownership threshold;
- a `DEFERRED` sync/network/ACK-read outcome resets the lease-busy streak while retaining bounded retry/backoff;
- fewer than six consecutive `LEASE_BUSY` outcomes simply retry;
- on the sixth consecutive `LEASE_BUSY`, if the control repository is a known active worker, the supervisor pauses only **new control-repository admission**; unrelated repositories remain eligible for available worker slots;
- the pause remains until control can be successfully serviced/probed, preventing a continuous control-repository queue from reacquiring the lease before global control is checked;
- on the sixth consecutive `LEASE_BUSY` with no corresponding known active control worker, the existing defensive **global drain** remains;
- a confirmed `PENDING` global request always triggers immediate global drain regardless of these counters.

This policy lives in pure `local_agent.supervisor.scheduling` state/decision helpers. `orchestrator.py` applies the resulting side effects; resource locks, claims, hard binding, self-update and emergency-disable mechanisms are unchanged.

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
  --max-workers 4
```

Inspect the loaded service:

```bash
.venv/bin/python scripts/macos_launchd.py status
```

Only when it is safe to interrupt active work, explicitly regenerate and restart the LaunchAgent:

```bash
.venv/bin/python scripts/macos_launchd.py restart \
  --mode parallel \
  --max-workers 4
```

`install` and `restart` are intentionally separate operations. A configuration write must never silently interrupt an active Local Agent task.

All modes use the same `com.michal.local-agent` label and are replacement configurations, never additional concurrent services. `parallel` is the production default, `multirepo` is the serial fallback and `single` is the direct daemon mode.

Cold-start rollout should begin disabled when the release changes binding/emergency/process-lifecycle boundaries. Verify the relevant release gates before leaving execution enabled.

Rollback to `agent_multirepo.py` does not weaken hard binding: the serial repository worker enforces the same registry/control/task equality. Do not roll back to a pre-hard-binding binary while bound task queues are considered trusted.

## Release flow

### Interrupted self-update recovery

Updates record original and candidate revisions in `~/Library/Application Support/local-agent/installation-pending.json` before changing the checkout. The installation lock prevents the guard from interrupting validation. Failed validation rolls back and clears the journal; process interruption leaves it durable. The guard persists `disabled` with reason `interrupted_self_update`, and supervisor startup and local enable refuse an unfinished installation.

Recovery is explicit: stop the service while disabled, inspect and preserve the journal and any unexpected checkout changes, restore its recorded original revision (or complete full verification of the installed candidate), and only then remove the journal. Restart disabled and inspect the installed revision/status before explicit local enable. Never delete the journal merely to bypass validation. A runtime reset does not clear installation state.

Remote emergency polling remains active during an installation transaction. Local enable never clears an incomplete transaction.

### Candidate gates

For non-trivial runtime changes:

1. use an isolated candidate branch/worktree based on current `main`;
2. implement the smallest coherent change with clean ownership boundaries;
3. bump the release version and add matching release notes/changelog before final verification;
4. run focused positive/negative tests for changed policy/state transitions;
5. for scheduler/control admission changes, require a real long-running control-repository overlap regression that crosses the six-consecutive-`LEASE_BUSY` threshold;
6. review `main...candidate` for architecture, unintended behavior and serial/resource/emergency/self-update regressions;
7. require full exact-SHA CI: compile, Ruff, full unittest/integration, coverage, Python 3.14 and Bridge browser;
8. require exact-SHA macOS ARM64 smoke containing changed scheduler policy and integration tests;
9. run current-documentation/release-metadata contract checks and audit all current operational docs, not just touched files;
10. audit planner-facing Local Agent docs in every registered downstream repository;
11. record three independent pre-merge verification passes on the exact final SHA;
12. advance `main` only after an explicit release decision;
13. tag released `main` `vX.Y.Z` matching `local_agent.version.RELEASE_VERSION`;
14. verify the running production version/revision and at least one real repository task after rollout;
15. remove obsolete candidate branches/worktrees after release is established.

Hard-binding releases additionally require missing/wrong binding rejection on both parallel and serial execution paths, control-binding mismatch admission failure, Chat Bridge unbound/rebind tests, active `cancel_task`, and global `disable` E2E.

## Downstream documentation gate

Current execution targets are LiteGraph, Growbox ML Controller, MatrixHub and Tracker. Standalone `esp32-c6-zigbee` execution has been removed from the agent registry/catalog; active C6 development belongs to LiteGraph. Changes to task schema, planner flow, status/control or execution model require a downstream docs audit before release. See `AGENTS.md` for exact files/branches.

Downstream task examples must include `agent_binding` for executable Chat Bridge/Local Agent work and must not instruct a conversation to select/switch repositories from model context.

## Source of truth

1. exact Local Agent terminal command/result output;
2. target repository source/tests;
3. remote run/result/status/control evidence;
4. planner analysis.

## Verification and log discipline

Use focused regression during iteration, then one bounded full suite near the end. Long/noisy structured stages may use `output_policy: "summary"`; bounded raw evidence remains in terminal results.

Unexpected worker exits back off 2-300 s and reset after normal outcomes. Deferred global-control work backs off 2-15 s. Only six **consecutive** `LEASE_BUSY` outcomes activate lease-ownership starvation protection in v4.18.14; degraded probe outcomes break that streak. Known active control-worker contention pauses only new control-repository admission, while unexplained contention retains the defensive global drain.

The production supervisor bounds `~/Library/Logs/local-agent.log` and `local-agent-error.log`. Routine successful internal Git housekeeping is quiet by default; actionable control failures, timeouts, nonzero internal commands, task lifecycle and other degraded states remain logged. Set `LOCAL_AGENT_VERBOSE_LOGS=1` only for temporary low-level diagnostics.
