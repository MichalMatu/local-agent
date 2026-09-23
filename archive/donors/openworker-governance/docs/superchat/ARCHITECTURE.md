# Superchat architecture

## Scope

Superchat is a higher-level planner supervisor above Chat Bridge. It manages long-running goals that may span multiple ChatGPT conversations while preserving Local Agent's existing deterministic execution boundary.

It is intentionally split into two parts:

1. a Superchat LLM conversation that can choose goals and supervisory actions;
2. deterministic supervisor infrastructure that validates and executes those lifecycle actions.

The supervisor infrastructure belongs above Chat Bridge. It does not belong in `local_agent/foundation`, the Local Agent runtime executor or repository workers.

## Non-negotiable invariants

- One concrete ChatGPT conversation remains bound to one immutable `agent_binding` and one repository.
- A replacement conversation gets a fresh ChatGPT/bridge conversation id.
- Rollover preserves repository identity but never copies the old `LA_CHAT` identity.
- Existing operator-only Rebind remains explicit and is not exposed as a Superchat action.
- Superchat cannot directly queue project `.agent/tasks` files. A bound child planner remains responsible for planning project work.
- Exact repository/task/result evidence is authoritative. Handoff text is advisory context only.
- Every lifecycle operation with external effects is idempotent and journaled before the first effect.
- At most one worker generation is authoritative for one goal.
- Recovery after browser/service-worker restart is a first-class path, not an exception.

## Durable state domains

The current Chat Bridge schema stores settings plus `conversations`. Superchat should add separate state domains rather than overload conversation records.

Suggested schema v4 shape:

```json
{
  "schemaVersion": 4,
  "settings": {},
  "conversations": {},
  "supervisor": {
    "enabled": false,
    "conversationId": null,
    "bindingRevision": 0,
    "generation": 0
  },
  "goals": {},
  "operations": {}
}
```

### Goal

A goal survives chat replacement.

```json
{
  "goal_id": "matrix-display-refactor",
  "repository_id": "matrixhub",
  "repository": "MichalMatu/MatrixHub",
  "agent_binding": "<canonical-uuid>",
  "status": "running",
  "generation": 3,
  "active_chat_id": "<bridge-chat-id>",
  "chat_history": ["<g1>", "<g2>", "<g3>"],
  "checkpoint": {
    "objective": "...",
    "completed": [],
    "remaining": [],
    "last_task_id": null,
    "last_commit": null,
    "verified_evidence": [],
    "blockers": [],
    "next_action": "...",
    "updated_at": "..."
  },
  "rollover_operation_id": null
}
```

Recommended goal states:

```text
IDLE
PLANNED
STARTING
RUNNING
CHECKPOINTING
ROTATING
BLOCKED
COMPLETED
FAILED
NEEDS_SUPERVISOR
```

### Worker generations

A conversation is one generation of a goal:

```text
goal
  -> generation 1 / chat A / retired
  -> generation 2 / chat B / active
  -> generation 3 / future
```

`goal.generation` is a monotonic lifecycle generation and is separate from the existing per-conversation scheduling generation.

### Operation journal

External lifecycle actions need durable idempotency keys.

Examples:

```text
spawn:goal-17:g1
checkpoint:goal-17:g1:42
rotate:goal-17:g1-to-g2
bootstrap:goal-17:g2
retire:goal-17:g1
```

Suggested rollover operation:

```json
{
  "operation_id": "rotate:goal-17:g1-to-g2",
  "kind": "rollover",
  "goal_id": "goal-17",
  "state": "creating_replacement",
  "from_chat_id": "chat-a",
  "from_generation": 1,
  "to_generation": 2,
  "candidate_tab_id": 123,
  "candidate_url": null,
  "candidate_chat_id": null,
  "checkpoint_revision": 42,
  "started_at": "...",
  "attempts": 1,
  "last_error": null
}
```

Suggested operation states:

```text
REQUESTED
SNAPSHOTTED
CREATING_REPLACEMENT
BOOTSTRAPPING
WAITING_FOR_CONCRETE_URL
REPLACEMENT_REGISTERED
ACTIVATING
OLD_WORKER_RETIRED
COMPLETED
FAILED
```

## Hard exhaustion versus proactive rotation

These are different transactions.

### Proactive rotation

If the old conversation is still usable, preserve it until the replacement is durably registered. The old worker may be asked to emit a fresh checkpoint before rotation.

### Hard maximum-length exhaustion

The observed terminal ChatGPT state means the old conversation can no longer be relied on to produce a handoff. Therefore correctness must not depend on a final summary from the exhausted chat.

Superchat must maintain a usable checkpoint before terminal exhaustion. On a hard terminal event, replacement bootstrap uses:

1. the latest durable goal checkpoint;
2. immutable repository/binding metadata;
3. exact current repository and Local Agent evidence that the new planner re-verifies before continuing.

This is why checkpointing is part of the minimum viable architecture, not an optional polish feature.

## Supervisor protocol boundary

Existing child controls (`[LAB:*]`) are intentionally same-conversation controls and must stay that way.

Superchat needs a separate protocol namespace, for example `[LAS:*]`, parsed by a dedicated module. Candidate actions:

```text
START_GOAL
WAKE_GOAL
PAUSE_GOAL
ROTATE_GOAL
STOP_GOAL
MARK_BLOCKED
REQUEST_CHECKPOINT
```

The exact syntax is still a research item. Requirements:

- strict parser;
- bounded fields;
- no free-form repository identity;
- repository/binding selected only from known catalog state;
- action accepted only from the configured supervisor conversation;
- sender URL, frame, supervisor binding revision and assistant baseline validated;
- idempotency key attached to any external effect;
- unknown action or malformed payload fails closed.

A normal child chat must never be able to mutate another child conversation.

## Replacement conversation transaction

Opening a tab is trivial. Recoverable registration is the real operation.

Expected path:

```text
persist rollover operation
        |
        v
open or navigate to ChatGPT new-chat UI
        |
        v
wait for a clean usable composer
        |
        v
submit continuation bootstrap
        |
        v
wait for concrete /c/<new-id>
        |
        v
validate new URL and selected catalog binding
        |
        v
persist new conversation record
        |
        v
atomically activate new goal generation
        |
        v
retire old conversation when applicable
        |
        v
complete operation journal entry
```

The current normal delivery path deliberately requires an already-known concrete conversation URL. Do not weaken that contract. Add a separate creation/bootstrap path for unbound new-chat pages.

## Recovery rules

On service-worker startup:

1. load schema v4 state;
2. inspect every non-terminal operation;
3. reconcile candidate tab/url state before creating anything new;
4. if a concrete replacement chat already exists, register/reuse it;
5. if the external effect is ambiguous, stop in `NEEDS_SUPERVISOR` rather than spawning duplicates;
6. never delete historical chat records during automatic recovery.

## Retry and circuit breaker

Suggested initial bounds:

```text
max_spawn_attempts = 3
max_rotation_attempts = 2
```

Use bounded backoff. Once exhausted, move the goal to `NEEDS_SUPERVISOR` and surface the exact failed operation and evidence.

## Security model

Superchat is more privileged than a child planner because it can affect multiple conversation lifecycles. That privilege must remain narrow:

- it manages Chat Bridge lifecycle only;
- it cannot mutate an existing repository binding;
- it cannot bypass the runtime agent catalog;
- it cannot execute Local Agent tasks directly;
- it cannot bypass global emergency controls;
- it cannot silently erase operation history.

The deterministic supervisor should be able to reject an unsafe or stale LLM request without asking the model to reinterpret it.
