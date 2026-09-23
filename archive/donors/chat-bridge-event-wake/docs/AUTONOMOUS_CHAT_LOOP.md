# Autonomous Chat Planner Loop

This document defines the optional autonomous planning loop connecting one ChatGPT conversation to one deterministic `local-agent` repository through Chat Bridge 0.5 and the Git-backed control plane.

## Hard identity invariant

Chat Bridge 0.5 is fail-closed and enforces:

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

The stored binding is immutable during normal conversation updates. The normal popup changes repository identity by removing the conversation and adding it again with the intended binding. The privileged operator Rebind path remains binding-revision aware for migration/testing: it increments `bindingRevision`, records a new `bindingSetAt`, clears conversation control dedupe state and forces a fresh bootstrap.

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
Chat Bridge 0.5
- stores exact immutable conversation binding
- sends binding envelope + bootstrap/wake prompt
- schedules only bound conversations
- tracks an exact WAIT_TASK watch when requested
- never chooses repository work
        |
        v
ChatGPT planner
- works only on the bound repository
- reads exact status/run/result/source evidence
- edits directly through GitHub when diff/CI evidence is sufficient
- creates local tasks with the bound agent_binding when execution is needed
        |
        v
local-agent
- verifies registry/control/task binding equality
- validates immutable task payload
- executes deterministic commands under runtime limits
- publishes status/run/result evidence
- emits a local bounded result-ready notification only after result push succeeds
        |
        +----> Native Messaging wake hint -> exact bound conversation
        |
        +----> scheduled reconciliation fallback
```

The bridge is transport and scheduling only. ChatGPT remains the planner. `local-agent` remains the deterministic executor; no LLM or heuristic planning layer belongs inside the executor.

The `local-agent` binding is deliberately `execution_enabled: false`. A conversation bound to it is bridge/operator-only: it may inspect/operate Local Agent infrastructure, but it must not create project task files for Growbox, MatrixHub, LiteGraph, Tracker or any other repository.

## Runtime schema 3

Chat Bridge state uses schema version 3. The remote runtime also uses schema 3 with an explicit agent catalog:

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

Repository ids, repository names and binding UUIDs must each be unique. A binding UUID must be canonical lowercase UUID text. Only runtime schema 3 is accepted and `execution_enabled` must be a JSON boolean. Missing, invalid or unavailable runtime configuration prevents sending (`runtime_unavailable`); there is no replacement identity catalog.

Event-wake persistence intentionally uses a separate bounded state object instead of changing schema 3. The event path is a continuation optimization and does not alter repository authority or task authority.

## Bootstrap, baseline and compact wakes

A newly added or explicitly rebound conversation receives one bootstrap prompt on its first actual wake. Later alarms send a compact wake prompt. Every prompt is prefixed with the binding envelope and hard-binding policy.

When the operator adds a chat, Bridge records the identity of the latest assistant answer already present in the conversation as `assistantBaseline`. That existing answer cannot become a control after the chat is added. Any **new** assistant answer after the add can use the complete `[LAB:*]` assistant control protocol immediately, even while the first bootstrap is still pending. This means a freshly added chat can be paused, resumed, stopped, paced, armed with `WAIT_TASK`, or given an explicit `NEXT` without requiring `Run now` first.

User-authored `LAB:OP:*` mutations use a separate safety baseline. When the current content script activates or is reinjected, the latest user message already present in the DOM is treated as historical and is never executed as a newly observed operator command. SPA navigation to another conversation establishes a new user-message baseline for that conversation. Only a new user-authored operator marker observed after the active content script/baseline may mutate Bridge state.

A privileged Rebind uses a new `bindingRevision` and still blocks old/pre-rebind controls until the new bootstrap establishes the new baseline.

On every wake, the planner must:

1. trust the bridge envelope as the conversation's routing identity;
2. inspect only that repository's latest daemon status and exact task evidence;
3. never inspect, queue, cancel or execute work for another repository as a substitute;
4. avoid queueing a second task for the same active goal while its current task is running;
5. inspect the exact terminal result before deciding the next bounded action;
6. treat `[LA_EVENT=task_result_ready]` only as a wake hint, never as proof of success/failure;
7. pause instead of switching repository when the goal appears to require another binding;
8. keep no-change wake turns terse.

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

Local execution is queued by committing a new unique task file to the bound repository's `agent-control` branch. Never hand-edit the daemon's local control clone.

## Choose GitHub or local execution

The planner may read and edit the bound repository directly through an available GitHub tool with the required permissions. Use this path for bounded source, configuration or documentation changes when review of the exact diff and relevant CI checks can verify the result. A GitHub commit proves a change, not successful execution; report the exact commit and completed checks.

Use Local Agent when the action needs command execution on the Mac, local build/test tools, device access or other machine-specific evidence. A hybrid flow may commit through GitHub and then queue a read-only verification task for that exact source SHA. Check the bound repository's active task first and avoid concurrent writes to the same branch while a local task is modifying it. Follow the repository's own branch policy.

Every local task still requires a unique immutable id, the exact `agent_binding`, explicit `resources` and bounded execution. Direct GitHub edits do not require an artificial executor task merely to record that they happened. The immutable conversation binding applies to both paths. The `local-agent` catalog entry remains unavailable for project execution; infrastructure edits follow its release policy.

## Autonomous turn algorithm

For every bridge wake:

1. Parse and retain `LA_AGENT`, `LA_REPO`, `LA_REPOSITORY` and `LA_CHAT` from the bridge prompt.
2. Do not derive a different target repository from conversation history.
3. Read the bound repository's current `.agent/status/daemon.json` and exact run/result evidence for the active goal.
4. If the relevant task is active and healthy, queue nothing else for that goal. If no exact task watch is armed yet, use `[LAB:WAIT_TASK=<task-id>]` for that exact task. If exact live evidence already proves that the active task cannot achieve its intended outcome, publish one repository-scoped `cancel_task` request for that exact task id instead of waiting for its timeout; then wait for the terminal cancellation/result evidence before replacing it.
5. If a terminal result exists, inspect its exact digest/result/command evidence. A result-ready event never replaces this step.
6. Choose direct GitHub work or local execution using the rules above. If local execution is needed, create one new bounded task with a unique id and exactly the wake's `agent_binding`, then normally end the turn with `[LAB:WAIT_TASK=<task-id>]` for the exact queued id.
7. If the task fails deterministically, diagnose the evidence and create a new task only when the failure supports a specific fix. Never replay or mutate the old payload.
8. If another repository is required, use `PAUSE`; do not switch/rebind automatically.
9. If the goal is complete with relevant exact-commit CI or terminal local execution evidence, use `STOP`.
10. Use `NEXT` only when an independent time-based recheck is actually useful; do not use it merely to discover whether a healthy watched task has completed.

The planner loop is sequential per active conversation goal, not globally serial. Independent bound conversations may proceed concurrently; `local_agent/supervisor/orchestrator.py` owns repository/resource concurrency.

## Active-task cancellation

`cancel_task` already exists as executor control; it is not a Chat Bridge UI shortcut. The planner may publish it only in the same bound repository and only for the exact task id supported by current run/status evidence:

```json
{
  "id": "cancel-<unique-id>",
  "action": "cancel_task",
  "task_id": "<exact-active-task-id>"
}
```

Use cancellation when current evidence makes failure unavoidable or proves that the task's premise is wrong, not merely because a task is taking longer than expected. An accepted active cancellation is owned by the worker executing that exact repository/task. Do not queue a replacement until the remote ACK and terminal task evidence establish what happened. Direct task cancellation is deliberately not part of the Browser Bridge LAB command plane; adding it would require a separate trusted repository-write transport.

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

`resources` remains mandatory and follows `docs/OPERATIONS.md`. Task ids/payloads are immutable within a repository. A new continuation uses a new id. The planner must never consider queueing itself proof of success; terminal result evidence is authoritative.

## Evidence order

For local execution, use evidence in this order:

1. terminal result for exact task id/digest;
2. live run/progress for the exact attempt;
3. current bound-repository daemon status;
4. source/diff/test evidence referenced by the result;
5. planner analysis.

Binding failures are terminal safety evidence, not retry candidates with altered routing. Correct the operator/catalog/control configuration or explicitly change the conversation binding instead.

## Post-queue liveness and event-driven wake

After queueing a Local Agent task, normally arm the exact task watch:

```text
[LAB:WAIT_TASK=<task-id>]
```

`WAIT_TASK` persists a watch scoped to the exact conversation repository id, repository name, `agent_binding` and task id. When Local Agent successfully pushes terminal `.agent/results/<task-id>.json`, it records a bounded local `task_result_ready` event. A Chrome Native Messaging host replays that event to Chat Bridge. Bridge persists the event before ACK, matches it to at most one exact watch and schedules the owning conversation immediately.

The event is a **wake hint only**. The resulting prompt contains:

```text
[LA_EVENT=task_result_ready]
[LA_TASK=<task-id>]
```

The planner must then read the exact terminal result from the bound repository before deciding what happened.

Event-driven waiting never removes scheduled reconciliation. `WAIT_TASK` also leaves a normal bounded alarm fallback. If Native Messaging is absent, disconnected, incompatible, paused, Master-off, or Chrome restarts, the Local Agent outbox and Bridge event state are durable and the normal alarm remains the recovery path. Therefore an early `NEXT` solely to poll healthy task completion is redundant.

Use `NEXT` for a genuinely time-based recheck, for example when waiting on an external condition that is not represented by a Local Agent terminal task event. Compatibility values such as `[LAB:NEXT=30s]` remain accepted, but they are not the normal healthy-task completion mechanism.

`PAUSE`, operator disable and Master-off retain the exact task watch but suspend Native Messaging so the host does not remain alive while delivery is disabled. On resume/re-enable/Master-on, Bridge reconnects and replays any durable outbox event. `STOP`, removal and rebind clear the old watch.

A fast task may finish before the assistant's `WAIT_TASK` marker is observed. This race is closed by the Local Agent durable outbox plus the Bridge recent-event cache: after the watch is registered, a matching already-published event is promoted immediately to a pending wake.

## LAB command plane

`control_protocol.js` owns one formal LAB command catalog. Assistant controls and user-authored operator mutations are separate privilege domains.

Assistant-safe discovery/diagnostic commands:

```text
[LAB:HELP]
[LAB:CAPABILITIES]
[LAB:STATUS]
[LAB:DEBUG]
[LAB:SETTINGS]
[LAB:CHATS]
[LAB:CHAT=<chat-id>]
```

These commands return a Bridge-generated user message beginning with `[LA_BRIDGE_FEEDBACK]`. That message is **read-only local evidence**, not operator approval. `HELP` exposes the live installed command catalog. `CAPABILITIES`, `STATUS` and `DEBUG` expose bounded event-wake diagnostics including native transport state, the current task watch and pending wake for this conversation. They do not expose task command output or create executor authority. Global `CHATS` and cross-chat `CHAT=<id>` inspection are available only when the current conversation is bound to the non-executing `local-agent` infrastructure binding; ordinary project chats are current-chat-only.

Assistant Bridge-local maintenance commands:

```text
[LAB:RELOAD=CONTENT]
[LAB:RELOAD=BRIDGE]
[LAB:RESTART=WORKER]
```

`RESTART=WORKER` is an alias for Bridge runtime/extension reload. It must never be interpreted as permission to restart the Local Agent supervisor. `RELOAD=CONTENT` refreshes only the exact current ChatGPT tab through the worker-owned dispose/inject/re-probe path.

Assistant scheduling controls include:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:WAIT_TASK=<task-id>]
[LAB:NEXT=2m]
[LAB:NEXT=10m]
[LAB:INTERVAL=30m]
[LAB:INTERVAL=AUTO]
```

User-authored Bridge mutations use a distinct namespace:

```text
[LAB:OP:ADD=<repository-id>]
[LAB:OP:REMOVE]
[LAB:OP:ENABLE]
[LAB:OP:DISABLE]
[LAB:OP:INTERVAL=<minutes|AUTO>]
[LAB:OP:RELOAD=CONTENT]
[LAB:OP:RELOAD=BRIDGE]
```

The assistant parser rejects `LAB:OP:*`. The operator scanner reads only the latest `data-message-author-role="user"` DOM message and the worker independently requires the same extension id, top frame and exact normalized conversation URL. `OP:ADD` resolves one exact repository id from the runtime catalog and creates the current chat disabled; it never guesses or implicitly rebinds. To change an existing binding, the operator removes the current chat and explicitly adds it with the desired repository id.

Already executed operator controls are persistently deduplicated in a bounded cache. Separately, the latest user message present when the current shared content protocol activates/reinjects is baseline-only and is not executed; SPA navigation establishes a new baseline before scanning the destination conversation. These rules prevent install/reload/reinjection/navigation from replaying historical `LAB:OP:*` mutations.

A bridge control is accepted only when the final marker/suffix satisfies the strict syntax in `chat_bridge/README.md`. Compatibility forms using `LOCAL_AGENT_BRIDGE:` remain accepted for the assistant namespace. Only the last candidate marker is considered; malformed final candidates do not fall back to earlier markers.

Assistant scheduling semantics:

- `STOP`: disable this conversation, clear its interval override and clear its task watch/pending event wake.
- `PAUSE`: disable this conversation while preserving its interval override and exact task watch; Native Messaging is suspended while paused.
- `RESUME`: re-enable this conversation; reconcile a retained pending event first or reconnect Native Messaging for a retained watch.
- `WAIT_TASK=<task-id>`: persist one exact watch for the current bound repository/binding/task tuple, connect the read-only native event transport when delivery is enabled, and keep a bounded scheduled reconciliation alarm as fallback.
- `NEXT=<duration>`: set `enabled=true` and arm/re-arm one conversation for a one-shot time-based wake; the compatibility protocol accepts 30 seconds through 24 hours. It is not the normal healthy Local Agent task completion mechanism.
- `INTERVAL=<minutes>`: set a persistent conversation pacing override.
- `INTERVAL=AUTO`: return to configured runtime pacing.

Per-chat operator settings are ordinary conversation state rather than a permanent operator lock. A later assistant scheduling control may overwrite the chat's manual pause/enabled state, next-wake timing or interval override. The global Bridge **Master** switch remains operator-only and is not mutable through assistant-safe LAB controls. No assistant marker can change repository binding.

## Completion and pause policy

Stop only when the requested outcome is supported by execution evidence. Executor `idle` means capacity is free; it does not create new scope.

Pause rather than guess when progress requires user action, external approval, unavailable credentials/hardware, a materially unresolved product choice, or work in another repository.

Cancel an active task instead of passively waiting for its timeout only when exact current evidence already proves that the task cannot produce the intended result. Cancellation is a bounded executor action, not a substitute for impatience.

## Required end-to-end validation

A hard-binding/event-wake rollout is complete only after all of these are demonstrated:

1. schema-3 runtime/catalog loads and a newly configured conversation stores one exact binding;
2. normal edits cannot change that conversation's repository/binding;
3. a privileged binding revision change forces bootstrap and rejects old-revision controls;
4. an unbound/migrated conversation has no scheduled wake;
5. a task with the correct binding executes and publishes terminal evidence;
6. a task with a missing binding is terminally rejected before claim/command execution;
7. a task with another repository's binding is terminally rejected before claim/command execution;
8. registry/control binding mismatch blocks repository admission;
9. the serial fallback preserves the same binding enforcement;
10. active `cancel_task` is observed through a remote-grounded ACK and terminates the targeted active task;
11. global `disable` prevents admission and can terminate active execution according to the emergency-control contract;
12. two conversations retain independent alarms/control state and cannot alter each other's binding through assistant controls;
13. assistant controls can overwrite operator-set per-chat pause/interval/timing state, but cannot change the global Bridge Master switch;
14. assistant LAB controls cannot execute `LAB:OP:*` mutations;
15. content activation/reinjection and SPA navigation do not replay a historical user-authored operator marker;
16. a `local-agent` infrastructure conversation may inspect global Bridge chat routing metadata while a project-bound conversation remains current-chat-only;
17. a short task that publishes before `WAIT_TASK` registration is recovered from the durable outbox/recent cache;
18. success, failure, rejection and cancellation terminal results all use the same non-authoritative result-ready wake path;
19. service-worker restart before and after native receive preserves the exact watch/pending wake;
20. missing tab, busy generation or send-button failure cannot consume a pending event;
21. pause, Master-off and operator disable suspend Native Messaging without deleting the exact watch;
22. another repository/binding/task tuple cannot wake the conversation;
23. Native Messaging absence still leaves scheduled reconciliation functional.

Canonical executor and rollout rules remain in `AGENTS.md` and `docs/OPERATIONS.md`.

## Delivery behavior in Bridge 0.5

Chat Bridge uses one shared content protocol version owned by `control_protocol.js`; content, worker, popup and tests consume that one value. Protocol bumps are deliberate when content behavior changes so a current worker can distinguish and replace already-open stale protocol tabs without duplicating protocol constants across modules.

The worker owns content activation for both scheduled delivery and popup onboarding. A missing or mismatched reachable content script is replaced without requiring a normal ChatGPT page reload: the worker disposes the current Bridge listener/timers and the exhaustion guard, injects `control_protocol.js`, `content_retry.js`, `content.js`, `dom_contract.js` and `exhaustion_guard.js`, then re-probes both content protocol and guard readiness. Popup code does not maintain a second protocol constant or its own `chrome.scripting.executeScript` policy.

The content script checks the exact conversation URL, protects operator drafts, authorizes normal wake delivery immediately before submission, and attempts to confirm the exact new user message in the DOM. Concurrent sends for the same conversation are rejected by an in-memory `delivery_in_progress` guard. Diagnostic `[LA_BRIDGE_FEEDBACK]` delivery remains local to the exact conversation and does not confer operator authority.

If Bridge inserted an exact wake but ChatGPT did not expose a usable Send button in time, the exact Bridge-owned prompt is left visible instead of being erased. If submission was attempted but the user-message DOM confirmation is missing, the exact retained prompt is also left alone. On a later run, Bridge may reuse a non-empty composer only when the previous conversation status is one of the documented recovery states **and** the composer text is byte-for-byte identical to the current Bridge prompt. Any operator edit, extra whitespace or unrelated draft fails closed and is never submitted automatically.

There is deliberately **no durable ambiguous-delivery journal**. `delivery_unconfirmed` remains diagnostic and does not deadlock normal chat operation. Event-wake state is different: an exact pending task event is durable until a delivery returns `ok`; transient delivery failure does not consume it.

Assistant control scanning is non-terminal on transient worker/message errors. The same unchanged assistant control is retried with bounded backoff until it is accepted or deterministically classified stale.

Browser fixture tests verify DOM submission, control/binding behavior, stale-content replacement, non-blocking retained-prompt recovery, operator replay baselining and worker restart in an isolated Chromium profile. They do not by themselves prove the current live ChatGPT DOM or the operator's currently loaded extension/native-host registration.
