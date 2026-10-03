# Local Agent Operations

This is the canonical operational workflow for `MichalMatu/local-agent`.

## Current production baseline

The production/runtime source is `~/local-agent` on `main`. Releases are tagged `vX.Y.Z`.

Current verified release:

```text
Local Agent 4.20.5
Chat Bridge 0.8.1
main = v4.20.5 = bd793d60c3bce4b247deb80a7e2bfc88e8bf4373
```

Production completed its natural self-update to that exact revision during the 2026-10-04 self-diagnostic. Always verify the installed `daemon_version` and `self_revision` from fresh daemon status; do not infer deployment from a source branch.

The bounded-parallel production supervisor is:

```bash
python agent_parallel.py --registry "$HOME/Library/Application Support/local-agent/repositories.json" --max-workers 4
```

`agent_multirepo.py` remains the direct serial fallback with concurrency one. Both enforce the same exact binding contract and share the daemon lock; they must never run simultaneously.

The immutable historical pre-BUG-002 rollback baseline remains:

```text
v4.18.13
= a32e54858c3bcb9687334b3232b71ae6ff130208
= rollback/v4.18.13-known-working
```

See `PRODUCTION_BASELINE_V4.18.13.md` for that historical context. Do not fabricate or back-date release tags during unrelated housekeeping.

## Hard agent-binding contract

Every executable repository has one canonical lowercase UUID `agent_binding`. The canonical catalog lives at:

```text
config/agent_bindings.json
```

For execution, the same identity must agree across:

```text
repositories.json entry
<repository control checkout>/.agent/binding.json
<agent-control>/.agent/tasks/<task-id>.json
```

The worker requires:

```text
registry binding == control binding == task binding
```

Failure is fail-closed before commands run. Missing/mismatched registry, control or task bindings do not become planner hints and are never repaired by rotating UUIDs.

Chat Bridge conversation metadata is not repository authorization. A parent Superchat may reason across donor and target repositories without Rebind. Every executable Local Agent task still uses the exact canonical binding of the selected target repository.

`local-agent` remains `execution_enabled: false`: it may be inspected/edited through direct GitHub operations, but must not receive Local Agent tasks.

## Superchat / Chat Bridge transport

A managed conversation is transport/scheduling identity only.

Remote runtime schema 3 publishes repository catalog/context plus `conversation_controls`. For an exact managed conversation, GitHub desired state is authoritative for:

- STATUS
- PAUSE
- RESUME
- NEXT
- INTERVAL

Each schedule mutation increments `control_generation`. Legacy repository/binding fields, planner scope and ADD/REBIND commands may remain for migration compatibility, but are not normal routing or authorization boundaries.

Production Bridge runtime state lives on:

```text
branch: chat-bridge-state
file:   chat_bridge/runtime.json
```

`chat-bridge-state` is operational desired state, not a development branch.

The previous parent control `chat-7781d9b9` was disabled during the 2026-10-04 self-diagnostic and should remain disabled unless intentionally reused.

## Conversation Fabric operator

The bounded operator namespace is:

```text
.agent/conversation/requests/<request-id>.json
.agent/conversation/results/<request-id>.json
```

These are reasoning/delegation control records, not executable tasks. `.agent/tasks` remains the only machine-execution repository contract.

Supervisor intake is default-disabled. It is enabled only when `LOCAL_AGENT_CONVERSATION_OPERATOR_ENABLED` is truthy and required isolated runtime paths are explicitly configured:

```text
LOCAL_AGENT_CONVERSATION_OPERATOR_ROOT
LOCAL_AGENT_CONVERSATION_OPERATOR_CHECKOUT
LOCAL_AGENT_CONVERSATION_OPERATOR_PRODUCTION_CHECKOUT
LOCAL_AGENT_CONVERSATION_OPERATOR_HOME   # optional
```

The 2026-10-04 production audit found Conversation Operator intake not enabled/configured. Enabling it is a deliberate rollout action, never an install side effect.

Child chats are reasoning-only and receive no independent machine authority.

## Current child-browser limitation

The implemented MVP child-spawn backend still uses the isolated browser actuator. A live pilot previously stopped with `chatgpt_login_timeout` before child registration.

The self-diagnostic isolated one concrete defect: login/session probing was gated by composer DOM visibility. Draft PR #135 decouples authentication readiness from composer readiness and has exact-SHA 5/5 green CI.

Do not return to long manual Chrome login / Cloudflare / DOM debugging. After an explicit merge/deploy decision, use one bounded pilot and continue only from fresh evidence.

## Repository control data

Each registered repository uses its own `agent-control` branch:

```text
.agent/binding.json
.agent/tasks/<task-id>.json
.agent/tasks/<task-id>.payload/**
.agent/runs/<task-id>.json
.agent/results/<task-id>.json
.agent/status/daemon.json
.agent/daemon/control.json
.agent/daemon/acks/*.json
```

Task ids/payloads are immutable within a repository. Interrupted claimed work is never silently replayed. Terminal results are durably spooled before publication; publication recovery may republish but may not re-execute commands.

For source-like or multiline payloads, prefer escape-safe `payload_file` references under `<task-id>.payload/` and publish manifest plus payload files atomically. See `TASK_PAYLOAD_TRANSPORT.md`.

## Parallel resource contract

Every task declares `resources` explicitly.

Typical project work:

```json
{"resources": [], "memory_limit_mb": 2048}
```

Shared named external resource:

```json
{"resources": ["shared:example-device"]}
```

Whole-host exclusivity:

```json
{"resources": ["machine"]}
```

`memory_limit_mb` is an independent RSS watchdog and does not imply machine exclusivity.

Resource acquisition occurs before claim/execution. Contention is WAIT, not task failure, and reports `waiting_resource` with bounded retry.

## Scheduler/control behavior

Production hard cap is four workers. Ordinary self-update waits for natural idle.

Repository workers never execute supervisor-wide restart/self-update. While workers are active, global control is probed and maintenance drains only when confirmed required.

Global-control probes distinguish:

```text
CLEAR
PENDING
LEASE_BUSY
DEFERRED
```

Only six genuinely consecutive `LEASE_BUSY` outcomes trigger starvation protection. If the control repository is a known active worker, only new admission for that repository is paused; unrelated repositories remain eligible. Unexplained ownership retains defensive global drain. Confirmed `PENDING` always drains safely.

## Process / recovery contract

- only one daemon/supervisor owns the daemon lock;
- task subprocesses are registered and owned by process groups;
- successful tasks may not leave background descendants;
- command, no-output, whole-task and RSS limits remain bounded;
- dirty workspaces are checkpointed before destructive cleanup;
- unexpected local control/workspace changes are never silently cleaned;
- final results are durable before publication;
- self-update accepts only validated clean fast-forward `main` and rolls back validation failure;
- active repository identities are never removed/mutated while workers or descendants may still use them.

## Local MCP operations

Machine-local MCP policy is independent from the repository registry. Default registry:

```text
~/Library/Application Support/local-agent/mcp/servers.json
```

Supported Streamable HTTP endpoints are loopback-only (`127.0.0.1`, `::1`, `localhost`). Remote/public MCP, OAuth and stdio are not supported by the current contract.

Static policy inspection:

```bash
.venv/bin/python -m local_agent.mcp.cli servers
```

Discovery:

```bash
.venv/bin/python -m local_agent.mcp.cli tools <server-id>
```

Read invocation:

```bash
.venv/bin/python -m local_agent.mcp.cli call <server-id> <tool-name> --arguments '{}'
```

Consequential local policies require matching explicit intent. See `MCP_INTEGRATION.md`.

## Development workflow

1. Read `AGENTS.md`, this file and target-repository planner instructions.
2. Establish exact target repository/binding identity from the current validated runtime catalog.
3. Inspect exact daemon/run/result state for that target.
4. Confirm the intended source branch.
5. Prepare the smallest deterministic change.
6. Classify resources explicitly.
7. Queue at most one active task for the current goal with exact target `agent_binding`, or use direct GitHub operations when host execution is unnecessary.
8. Follow the same task digest/attempt until terminal evidence exists.
9. Treat resource/capacity waiting as continuation, not completion.
10. Run focused verification first and one broad gate when warranted.
11. Publish source according to target repository policy.
12. Treat source publication and device/runtime verification as separate gates.

For Local Agent itself use:

```bash
python scripts/verify.py
python scripts/verify.py --only tests
python scripts/verify.py --profile macos-smoke
```

Because `local-agent` is execution-disabled as a Local Agent target, Local Agent source maintenance should use direct GitHub operations or an explicitly approved non-Local-Agent development environment.

## Multi-repository administration

Registry:

```text
~/Library/Application Support/local-agent/repositories.json
```

Administration commands:

```bash
python -m local_agent.repository.admin list
python -m local_agent.repository.admin validate
python -m local_agent.repository.admin provision --repository-id <id>
python -m local_agent.operator.local migrate-bindings
```

Provisioning is explicit, never a poll-loop side effect. Repository ids/remotes/bindings and normalized control/work/checkpoint paths remain disjoint and stable.

The first enabled registry entry is the supervisor control repository in registry v1; reordering it changes global restart/self-update/status control source.

Do not remove or identity-mutate active registry entries while workers/descendants may still be alive.

## Emergency controls

Global persistent disable and the central `operator-control` branch remain independent of project control-branch health.

`operator-control` is operational safety state, not a development branch.

Repository controls include cancellation/disable/status handling. Active cancellation is valid only for the exact active task and unacknowledged control id.

Emergency disable remains authoritative even during partial/broken binding migration.

See `EMERGENCY_CONTROLS.md`.

## Runtime bounds

Canonical defaults:

- command timeout: 900 s, max 7200 s;
- no-output timeout: 300 s, max 3600 s;
- whole-task budget: 1800 s, max 21600 s;
- finalization reserve: 60 s;
- normal RSS limit: 4096 MiB, configurable max 16384 MiB.

External task payload files do not relax logical task bounds.

## macOS deployment

LaunchAgent definitions are generated from the current checkout and user home. Machine-specific plist files with hard-coded user paths are not repository source.

See `deploy/macos/README.md` for install/update workflow.

Normal release deployment should prefer validated self-update and natural drain. Do not interrupt an active task solely to force a version transition.

## Observability

Routine successful Git synchronization/publication remains quiet; failures/retries remain visible. Supervisor logs task boundaries plus bounded idle heartbeat. launchd stdout/stderr and retained command output remain bounded.

Routine diagnostics should expose:

- exact daemon version/revision;
- supervisor/worker state and active task identity;
- repository registry/binding health;
- resource/admission state;
- Conversation Operator intake enabled/configured state.

Use `LOCAL_AGENT_VERBOSE_LOGS=1` only for temporary diagnostics.

## Release gate

A non-trivial runtime release requires:

1. isolated candidate from current `main`;
2. matching source version, release notes and changelog entry;
3. focused positive/negative verification;
4. exact architecture/diff review;
5. full GitHub CI on the exact candidate SHA;
6. macOS ARM64 smoke where applicable;
7. current-documentation/release-metadata checks;
8. explicit merge/advance of `main`;
9. matching `vX.Y.Z` tag;
10. validated deployment/self-update and live exact-version/revision verification;
11. candidate branch/worktree cleanup after production proof.

Historical dated handoffs, release notes and archived development branches are evidence only; they are not current operational authority.
