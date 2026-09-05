# Autonomous Chat Planner Loop

This document defines the optional autonomous planning loop connecting one ChatGPT conversation to one deterministic `local-agent` repository through Chat Bridge 0.4 and the Git-backed control plane.

## Hard identity invariant

Chat Bridge 0.4 is fail-closed and enforces:

```text
one ChatGPT conversation == one immutable agent_binding == one repository id == one GitHub repository
```

A normal wake must never infer or switch repository identity from model context. Every bound wake carries all four identity fields:

```text
[LA_AGENT=<canonical UUID>]
[LA_REPO=<repository id>]
[LA_REPOSITORY=<owner/name>]
[LA_CHAT=<conversation id>]
```

The stored binding is immutable during normal conversation updates. Changing repository identity requires the explicit operator **Rebind** action in the extension. Rebind increments `bindingRevision`, records a new `bindingSetAt`, clears conversation control dedupe state and forces a fresh bootstrap.

Unbound migrated conversations are disabled with `binding_required` and have no alarm. A runtime-catalog mismatch disables the conversation with `binding_catalog_mismatch`. The bridge must never guess a replacement binding.

`local-agent` independently enforces the executor side of the same identity. Before claim/execution, both the production parallel worker and the serial fallback require:

```text
registry agent_binding
    == .agent/binding.json agent_binding
    == task.agent_binding
```

A missing repository binding blocks admission as `unbound`. A control-branch mismatch blocks admission as `binding_error`. A missing/wrong task binding produces a terminal pre-claim failure (`agent_binding_missing` or `agent_binding_mismatch`) and executes no task command.

The global operator `disabled` state has higher priority than repository binding admission, so the emergency kill switch remains effective during migration or broken binding state.

## Roles

```text
user goal in one ChatGPT conversation
        |
        v
Chat Bridge 0.4
- stores exact immutable conversation binding
- sends binding envelope + bootstrap/wake prompt
- schedules only bound conversations
- never chooses repository work
        |
        v
ChatGPT planner
- works only on the bound repository
- reads exact status/run/result/source evidence
- creates only tasks containing the bound agent_binding
        |
        v
local-agent
- verifies registry/control/task binding equality
- validates immutable task payload
- executes deterministic commands under runtime limits
- publishes status/run/result evidence
        |
        +----> bridge wakes the same bound conversation
```

The bridge is transport and scheduling only. ChatGPT remains the planner. `local-agent` remains the deterministic executor; no LLM or heuristic planning layer belongs inside the executor.

The `local-agent` binding is deliberately `execution_enabled: false`. A conversation bound to it is bridge/operator-only: it may inspect/operate Local Agent infrastructure, but it must not create project task files for Growbox, C6, MatrixHub, LiteGraph or any other repository.

## Runtime schema 3

Chat Bridge 0.4 state uses schema version 3. The remote runtime also supports schema 3 with an explicit agent catalog:

```json
{
  "schema_version": 3,
  "interval_minutes": 10,
  "busy_retry_minutes": 1,
  "bootstrap_prompt": "...",
  "wake_prompt": "...",
  "agents": [
    {
      "repository_id": "matrixhub",
      "repository": "MichalMatu/MatrixHub",
      "agent_binding": "033327ab-700d-43b4-9b3b-caff1acaa2c7",
      "execution_enabled": true
    }
  ]
}
```

Repository ids, repository names and binding UUIDs must each be unique. A binding UUID must be canonical lowercase UUID text. Runtime schema 1/2 remains readable for compatibility, but it uses the extension's built-in canonical agent catalog. New production publication should use schema 3.

## Bootstrap and compact wakes

A newly bound or explicitly rebound conversation receives one bootstrap prompt. Later alarms send a compact wake prompt. Every prompt is prefixed with the binding envelope and hard-binding policy.

On every wake, the planner must:

1. trust the bridge envelope as the conversation's routing identity;
2. inspect only that repository's latest daemon status and exact task evidence;
3. never inspect, queue, cancel or execute work for another repository as a substitute;
4. avoid queueing a second task for the same active goal while its current task is running;
5. inspect the exact terminal result before deciding the next bounded action;
6. pause instead of switching repository when the goal appears to require another binding;
7. keep no-change wake turns terse.

A conversation still needs a stated active goal. The binding identifies where work may happen; it does not invent scope.

## Control-plane locations

Each executable repository has its own `agent-control` branch:

```text
.agent/binding.json               immutable repository binding identity
.agent/tasks/<task-id>.json       planner -> executor
.agent/runs/<task-id>.json        live execution evidence
.agent/results/<task-id>.json     terminal execution evidence
.agent/status/daemon.json         repository worker/daemon status
.agent/daemon/control.json        maintenance/status controls
.agent/daemon/acks/*.json         maintenance/status acknowledgements
```

Normal work is queued by committing a new unique task file to the bound repository's `agent-control` branch. Never hand-edit the daemon's local control clone.

## Autonomous turn algorithm

For every bridge wake:

1. Parse and retain `LA_AGENT`, `LA_REPO`, `LA_REPOSITORY` and `LA_CHAT` from the bridge prompt.
2. Do not derive a different target repository from conversation history.
3. Read the bound repository's current `.agent/status/daemon.json` and exact run/result evidence for the active goal.
4. If the relevant task is active, queue nothing else for that goal.
5. If a terminal result exists, inspect its exact digest/result/command evidence.
6. If a concrete next action is required, create one new bounded task with a unique id and exactly the wake's `agent_binding`.
7. If the task fails deterministically, diagnose the evidence and create a new task only when the failure supports a specific fix. Never replay or mutate the old payload.
8. If another repository is required, use `PAUSE`; do not switch/rebind automatically.
9. If the goal is complete, use `STOP`.
10. Otherwise use a suitable one-shot `NEXT` or allow normal pacing to resume.

The planner loop is sequential per active conversation goal, not globally serial. Independent bound conversations may proceed concurrently; `local_agent/supervisor/orchestrator.py` owns repository/resource concurrency.

## Task contract

Every task created by an executable bound conversation must include its exact `agent_binding`:

```json
{
  "id": "matrix-readonly-001",
  "agent_binding": "033327ab-700d-43b4-9b3b-caff1acaa2c7",
  "mode": "commands",
  "work_branch": "main",
  "allow_write": false,
  "resources": [],
  "command_timeout": 60,
  "task_timeout": 180,
  "commands": [
    "git status --short && git rev-parse --short HEAD"
  ]
}
```

`resources` remains mandatory and follows `docs/OPERATIONS.md`. Task ids/payloads are immutable within a repository. A new continuation uses a new id.

The planner must never consider queueing itself proof of success. Terminal result evidence is authoritative.

## Evidence order

Use evidence in this order:

1. terminal result for exact task id/digest;
2. live run/progress for the exact attempt;
3. current bound-repository daemon status;
4. source/diff/test evidence referenced by the result;
5. planner analysis.

Binding failures are terminal safety evidence, not retry candidates with altered routing. Correct the operator/catalog/control configuration or explicitly rebind the conversation instead.

## Post-queue liveness

After queueing a task, prefer one early re-check around 30 seconds:

```text
[LAB:NEXT=30s]
```

Use it only to catch immediate deterministic failure or failure to claim. If execution is healthy, return to a longer cadence appropriate for the remaining duration. Do not turn healthy multi-minute work into permanent 30-second polling.

## Conversation-scoped bridge controls

A bridge control is accepted only as the final non-empty line of the latest assistant message in the same configured conversation:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:NEXT=30s]
[LAB:NEXT=10m]
[LAB:INTERVAL=30m]
[LAB:INTERVAL=AUTO]
```

Compatibility forms using `LOCAL_AGENT_BRIDGE:` remain accepted.

- `STOP`: goal complete; disable this conversation and clear its interval override.
- `PAUSE`: manual/external action or repository rebind required.
- `RESUME`: re-enable this conversation; it does not change its binding.
- `NEXT=<duration>`: arm/re-arm one conversation for a one-shot wake; 30 seconds through 24 hours.
- `INTERVAL=<minutes>`: persistent conversation pacing override.
- `INTERVAL=AUTO`: return to configured runtime pacing.

The global bridge master switch may suspend all alarms but never alters bindings. No assistant marker can perform Rebind.

## Completion and pause policy

Stop only when the requested outcome is supported by execution evidence. Executor `idle` means capacity is free; it does not create new scope.

Pause rather than guess when progress requires user action, external approval, unavailable credentials/hardware, a materially unresolved product choice, or work in another repository.

## Required end-to-end validation for hard binding

A 0.4 rollout is complete only after all of these are demonstrated:

1. schema-3 runtime/catalog loads and a newly configured conversation stores one exact binding;
2. normal edits cannot change that conversation's repository/binding;
3. explicit Rebind changes it and forces bootstrap;
4. an unbound/migrated conversation has no scheduled wake;
5. a task with the correct binding executes and publishes terminal evidence;
6. a task with a missing binding is terminally rejected before claim/command execution;
7. a task with another repository's binding is terminally rejected before claim/command execution;
8. registry/control binding mismatch blocks repository admission;
9. the serial fallback preserves the same binding enforcement;
10. active `cancel_task` is observed through a remote-grounded ACK and terminates the targeted active task;
11. global `disable` prevents admission and can terminate active execution according to the emergency-control contract;
12. two conversations retain independent alarms/control state and cannot alter each other's binding without explicit operator Rebind.

Canonical executor and rollout rules remain in `AGENTS.md` and `docs/OPERATIONS.md`.
