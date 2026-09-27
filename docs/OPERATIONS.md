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

Current deployed production source identifies itself as v4.19.0 at `1ea863d06a20e766f9fe0fa5589cc59aa0e2671a`. The BUG-002 scheduler repair introduced with v4.18.14 behavior is established production behavior; v4.18.13 is retained only as the explicit pre-fix rollback baseline. See [`PRODUCTION_BASELINE_V4.18.13.md`](PRODUCTION_BASELINE_V4.18.13.md) for historical pre-fix context before changing scheduler/control admission behavior.

The remote tag set has historically contained release-tag gaps. Do not fabricate or back-date a release tag during unrelated housekeeping. The release-flow invariant below remains the rule for future releases; repairing historical tag metadata requires an explicit release-metadata decision against an exact commit.

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

Repository binding is operational identity. Do not rotate a UUID to repair a task or switch a chat. Every Chat Bridge conversation keeps one immutable conversation binding. Normal `planner_scope=repository` conversations may change that binding only through explicit **Rebind**/remove-add. An explicitly catalog-authorized `planner_scope=multirepo` conversation may select another current runtime-catalog target without changing its conversation binding; every Local Agent task still uses the exact canonical binding of the selected target repository. Executor configuration changes require an intentional disabled migration.

The canonical `host-ops` binding is the multirepo operator workspace. The `local-agent` catalog entry remains `execution_enabled: false`: a host-ops multirepo conversation may inspect or edit `MichalMatu/local-agent` through direct GitHub operations, but it must not queue a Local Agent task targeting the execution-disabled `local-agent` entry. See [`HOST_OPS_MULTIREPO.md`](HOST_OPS_MULTIREPO.md).

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

Legacy/unbound conversations migrate disabled with `binding_required`; they receive no alarm. Normal conversation edits cannot alter binding fields. Explicit Rebind changes the conversation binding and forces a new bootstrap. It is not required merely to change target repositories inside a validated `planner_scope=multirepo` conversation.

Remote runtime schema 3 publishes the canonical agent catalog plus optional `planner_scope`. The default scope is `repository`; only `repository` and `multirepo` are valid, and `multirepo` requires an execution-enabled operator binding. Production runtime is served from branch `chat-bridge-state`, file `chat_bridge/runtime.json`. Rollout order matters:

1. keep Local Agent globally disabled;
2. release/fast-forward Local Agent code and validate exact-candidate CI;
3. update/reload the matching Chat Bridge when the bridge contract changed;
4. publish runtime schema 3 with the matching catalog/scope data when runtime data changed;
5. verify migrated chats are fail-closed, normal chats preserve repository scope, and intended multirepo chats receive only their explicit catalog authorization;
6. run binding/planner-scope negative E2E plus emergency-control E2E when those boundaries changed;
7. enable Local Agent only after required checks are green.

Publishing a new bridge runtime before an old bridge is replaced is not a reason to enable execution. Older Bridge code ignores the optional scope field and therefore retains its existing stricter repository-only behavior until the matching worker code is loaded. The kill switch remains the safety boundary during rollout. Detailed current planner/Bridge semantics live in [`AUTONOMOUS_CHAT_LOOP.md`](AUTONOMOUS_CHAT_LOOP.md) and [`HOST_OPS_MULTIREPO.md`](HOST_OPS_MULTIREPO.md).

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

## Local MCP operations

Generic local MCP configuration is independent from the repository registry and is never committed to Git. The default file is:

```text
~/Library/Application Support/local-agent/mcp/servers.json
```

Before using MCP on a Local Agent installation, install the pinned runtime dependency into that checkout's virtual environment:

```bash
cd ~/local-agent
.venv/bin/python -m pip install --disable-pip-version-check -r requirements-runtime.txt
```

The initial MCP boundary supports only `streamable_http` endpoints whose host is exactly `127.0.0.1`, `::1`, or `localhost`. Remote/public-network MCP, OAuth and stdio are not supported. Stdio must not be introduced unless its child process is owned by the existing registered spawn/process-group lifecycle contract.

Inspect static machine policy without connecting:

```bash
.venv/bin/python -m local_agent.mcp.cli servers
```

Discover one configured server through the official SDK:

```bash
.venv/bin/python -m local_agent.mcp.cli tools <server-id>
```

Invoke a locally authorized read tool:

```bash
.venv/bin/python -m local_agent.mcp.cli call <server-id> <tool-name> --arguments '{}'
```

`write` and `arbitrary_code` policies additionally require exact matching `--intent write` or `--intent arbitrary_code`. Discovery metadata and MCP annotations never substitute for that local policy.

Text/structured output, discovery count, binary aggregate size and artifact count are bounded per server. Binary content is written under `~/Library/Application Support/local-agent/mcp/artifacts/` by default and normal output contains only path/MIME/size/SHA-256 metadata. Artifact MIME types must be explicitly allowed by machine policy.

The first live integration proof for a new application is read-only: record the actual loopback endpoint and `tools/list` evidence, enable only known safe read policies, invoke only read tools, and validate image/blob artifact metadata if present. Do not use the first smoke for write or arbitrary-code execution. See [`MCP_INTEGRATION.md`](MCP_INTEGRATION.md).

## Development workflow

1. Read `AGENTS.md`, this file and target-repository planner instructions.
2. Establish the exact target repository/binding identity before queueing anything. A multirepo planner resolves it only from the current validated runtime catalog.
3. Inspect `.agent/status/daemon.json` and exact run/result evidence for that target repository.
4. Confirm the intended `work_branch` when it differs from the default.
5. Prepare the smallest deterministic change.
6. Classify resources explicitly; current registered project repositories use `resources: []` and detect/verify devices inside task commands.
7. Queue one new unique task containing the target repository's exact `agent_binding` and explicit `resources`.
8. For healthy Chat Bridge/Local Agent work, perform the first liveness re-check no sooner than about two minutes; normally use 5-10 minute `NEXT` pacing for multi-minute builds/tests unless exact evidence supports a nearer completion.
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

An autonomous conversation follows one active task at a time for its current target/goal. Independent repositories/conversations may overlap when executor resource admission permits it.

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

The first enabled registry entry is the supervisor control repository in registry v1. Reordering entries therefore changes the global restart/self-update/status control source. The production policy introduced in v4.18.14 clears stale retry/lease-busy/pause state and invalidates the old poll clock when that identity changes.

Do not remove or identity-mutate an active registry entry while workers/descendants may still be alive.

## Emergency controls

Local operator commands are in `local_agent.operator.local` and [`EMERGENCY_CONTROLS.md`](EMERGENCY_CONTROLS.md). The global persistent disable marker and central `operator-control` branch remain independent of project control-branch health.

Repository controls include `cancel_task`, `disable` and status handling. Active-task control watching periodically synchronizes the target repository control branch. An active cancel is valid only when the fetched control request targets the exact active task and the control id is not already remotely acknowledged.

`disable` is global safety state, not merely a display status. When disabled, workers stop task admission even if task/binding data is otherwise valid.

Repository workers never execute supervisor-wide restart/self-update directly. While workers are active, the parallel supervisor probes global control and drains safely before confirmed global maintenance.

### Control-probe admission policy (introduced in v4.18.14)

The frozen v4.18.13 scheduler had confirmed BUG-002: a long task in the designated control repository legitimately owned its repository lease, so the periodic global-control probe returned `LEASE_BUSY`. Repeated expected ownership could trigger a global admission drain and block unrelated repositories even with `resources: []` and free worker capacity.

Current production behavior separates retry evidence from the lease-busy starvation streak:

- each deferred probe participates in bounded 2-15 second retry/backoff;
- only true **consecutive `LEASE_BUSY`** outcomes count toward the six-attempt lease-ownership threshold;
- a `DEFERRED` sync/network/ACK-read outcome resets the lease-busy streak while retaining bounded retry/backoff;
- fewer than six consecutive `LEASE_BUSY` outcomes simply retry;
- on the sixth consecutive `LEASE_BUSY`, if the control repository is a known active worker, the supervisor pauses only **new control-repository admission**; unrelated repositories remain eligible for available worker slots;
- the pause remains until control can be successfully serviced/probed, preventing a continuous control-repository queue from reacquiring the lease before global control is checked;
- on the sixth consecutive `LEASE_BUSY` with no corresponding known active control worker, the existing defensive **global drain** remains;
- a confirmed `PENDING` global request always triggers immediate global drain regardless of these counters.

This policy lives in pure `local_agent.supervisor.scheduling` state/decision helpers. `orchestrator.py` applies the resulting side effects; resource locks, claims, target-repository hard binding, self-update and emergency-disable mechanisms are unchanged.

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

Cold-start rollout should begin disabled when the release changes binding/planner-scope/emergency/process-lifecycle boundaries. Verify the relevant release gates before leaving execution enabled.

Rollback to `agent_multirepo.py` does not weaken target-repository hard binding: the serial repository worker enforces the same registry/control/task equality. Do not roll back to a pre-hard-binding binary while bound task queues are considered trusted.

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
6. for MCP changes, require a real hermetic loopback Streamable HTTP MCP server test covering official-SDK negotiation, discovery, invocation, timeout and bounded artifact/result paths;
7. for the first live MCP application target, preserve actual endpoint/tool-list evidence and run only explicit read-only smoke calls before release;
8. for planner-scope changes, prove normal repository scope remains isolated, invalid scope fails closed, the authorized multirepo workspace resolves only current catalog targets, and Local Agent tasks retain each target repository's exact canonical binding;
9. review `main...candidate` for architecture, unintended behavior and serial/resource/emergency/self-update regressions;
10. require full exact-SHA CI: compile, Ruff, full unittest/integration, coverage, Python 3.14 and Bridge browser;
11. require exact-SHA macOS ARM64 smoke containing changed scheduler policy and integration tests, including MCP HTTP tests when that boundary changes;
12. run current-documentation/release-metadata contract checks and audit all current operational docs, not just touched files;
13. audit planner-facing Local Agent docs in every registered downstream repository when their contract changed;
14. record three independent pre-merge verification passes on the exact final SHA;
15. advance `main` only after an explicit release decision;
16. tag released `main` `vX.Y.Z` matching `local_agent.version.RELEASE_VERSION`;
17. verify the running production version/revision and at least one real repository task after rollout;
18. remove obsolete candidate branches/worktrees after release is established.

Binding/planner-scope releases additionally require missing/wrong target binding rejection on both parallel and serial execution paths, control-binding mismatch admission failure, normal-scope and multirepo Bridge tests, active `cancel_task`, and global `disable` E2E.

## Downstream documentation gate

The canonical target set is defined by `config/agent_bindings.json`; do not maintain a second hand-written repository list here. Changes to task schema, planner flow, status/control or execution model require a downstream documentation audit before release. `AGENTS.md` defines the exact downstream files/branches that must remain synchronized.

Downstream task examples must include `agent_binding` for executable Chat Bridge/Local Agent work. Normal repository-scoped conversations must not select/switch repositories from model context; explicitly authorized multirepo conversations may change targets only through the current validated runtime catalog.

## Source of truth

1. exact Local Agent terminal command/result output;
2. target repository source/tests;
3. remote run/result/status/control evidence;
4. planner analysis.

## Verification and log discipline

Use focused regression during iteration, then one bounded full suite near the end. Long/noisy structured stages may use `output_policy: "summary"`; bounded raw evidence remains in terminal results.

Unexpected worker exits back off 2-300 s and reset after normal outcomes. Deferred global-control work backs off 2-15 s. Only six **consecutive** `LEASE_BUSY` outcomes activate lease-ownership starvation protection in the production policy introduced in v4.18.14; degraded probe outcomes break that streak. Known active control-worker contention pauses only new control-repository admission, while unexplained contention retains the defensive global drain.

The production supervisor bounds `~/Library/Logs/local-agent.log` and `local-agent-error.log`. Routine successful internal Git housekeeping is quiet by default; actionable control failures, timeouts, nonzero internal commands, task lifecycle and other degraded states remain logged. Set `LOCAL_AGENT_VERBOSE_LOGS=1` only for temporary low-level diagnostics.
