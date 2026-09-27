# Autonomous Chat Planner Loop

This document defines the optional autonomous planning loop connecting one ChatGPT conversation to deterministic `local-agent` repository execution through Chat Bridge 0.5 and the Git-backed control plane.

## Conversation binding and planner scope

Chat Bridge 0.5 is fail-closed. Every configured conversation stores one immutable canonical binding identity:

```text
one ChatGPT conversation
    == one immutable agent_binding
    == one bound repository id
    == one bound GitHub repository
```

The binding catalog also defines the planner scope attached to that binding:

```text
planner_scope=repository   -> work only on the bound repository
planner_scope=multirepo    -> work across validated runtime-catalog repositories
```

`repository` is the default. `multirepo` is explicit catalog authorization, not a repository-name heuristic. The canonical `host-ops` binding is the multirepo operator workspace. See `docs/HOST_OPS_MULTIREPO.md`.

Every bound wake carries the immutable conversation identity:

```text
[LA_AGENT=<canonical UUID>]
[LA_REPO=<repository id>]
[LA_REPOSITORY=<owner/name>]
[LA_CHAT=<conversation id>]
```

For repository scope, that identity is also the only allowed target repository. For multirepo scope, the envelope identifies the operator conversation while the target repository for each action is resolved separately from the current validated runtime catalog. The planner must never infer repository ids or binding UUIDs from prose, filesystem names, prior chats or model memory.

The stored conversation binding is immutable during normal conversation updates. The normal popup changes the conversation binding by removing the conversation and adding it again with the intended binding. The privileged operator Rebind path remains binding-revision aware for migration/testing: it increments `bindingRevision`, records a new `bindingSetAt`, clears conversation control dedupe state and forces a fresh bootstrap. Normal cross-repository work inside an authorized multirepo conversation does not use Rebind.

Unbound migrated conversations are disabled with `binding_required` and have no alarm. A runtime-catalog mismatch disables the conversation with `binding_catalog_mismatch`. The bridge must never guess a replacement binding or target identity.

`local-agent` independently enforces target-repository identity. Before claim/execution, both the production parallel worker and the serial fallback require:

```text
registry agent_binding
    == .agent/binding.json agent_binding
    == task.agent_binding
```

A missing repository binding blocks admission as `unbound`. A control-branch mismatch blocks admission as `binding_error`. A missing/wrong task binding produces a terminal pre-claim failure (`agent_binding_missing` or `agent_binding_mismatch`) and executes no task command. Multirepo planner scope does not alter this executor contract.

The global operator `disabled` state has higher priority than repository binding admission, so the emergency kill switch remains effective during migration or broken binding state.

## Roles

```text
user goal in one ChatGPT conversation
        |
        v
Chat Bridge 0.5
- stores exact immutable conversation binding
- loads validated planner scope + runtime catalog
- sends binding envelope + bootstrap/wake policy
- schedules only bound conversations
- never chooses repository work
        |
        v
ChatGPT planner
- stays inside the authorized planner scope
- resolves multirepo targets only from the current runtime catalog
- reads exact status/run/result/source evidence
- edits directly through GitHub when diff/CI evidence is sufficient
- creates local tasks with the target repository's exact agent_binding
        |
        v
local-agent
- verifies target registry/control/task binding equality
- validates immutable task payload
- executes deterministic commands under runtime limits
- publishes repository-scoped status/run/result evidence
        |
        +----> bridge wakes the same bound conversation
```

The bridge is transport and scheduling only. ChatGPT remains the planner. `local-agent` remains the deterministic executor; no LLM or heuristic planning layer belongs inside the executor.

The `local-agent` catalog entry is deliberately `execution_enabled: false`. A repository-scoped conversation bound directly to it is bridge/operator-only. A multirepo `host-ops` conversation may inspect and edit `MichalMatu/local-agent` through direct GitHub operations without rebinding, but it still must not create a Local Agent task targeting the execution-disabled `local-agent` entry. Self-execution is a separate security decision.

## Runtime schema 3

Chat Bridge 0.5 state uses schema version 3. The remote runtime also uses schema 3 with an explicit agent catalog:

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
    },
    {
      "repository_id": "host-ops",
      "repository": "MichalMatu/host-ops",
      "agent_binding": "16d688b6-b0ef-4905-a5bd-24e59c99cfb4",
      "execution_enabled": true,
      "planner_scope": "multirepo"
    }
  ]
}
```

Repository ids, repository names and binding UUIDs must each be unique. A binding UUID must be canonical lowercase UUID text. Only runtime schema 3 is accepted and `execution_enabled` must be a JSON boolean. `planner_scope` is optional and defaults to `repository`; only `repository` and `multirepo` are accepted, and an execution-disabled binding may not advertise `multirepo`. Missing, invalid or unavailable runtime configuration prevents sending (`runtime_unavailable`); there is no replacement identity catalog.

## Bootstrap, baseline and compact wakes

A newly added or explicitly rebound conversation receives one bootstrap prompt on its first actual wake. Later alarms send a compact wake prompt. Every prompt is prefixed with the binding envelope and the policy derived from the validated planner scope.

When the operator adds a chat, Bridge records the identity of the latest assistant answer already present in the conversation as `assistantBaseline`. That existing answer cannot become a control after the chat is added. Any **new** assistant answer after the add can use the complete `[LAB:*]` assistant control protocol immediately, even while the first bootstrap is still pending. This means a freshly added chat can be paused, resumed, stopped, paced or armed with `NEXT` without requiring `Run now` first.

User-authored `LAB:OP:*` mutations use a separate safety baseline. When the current content script activates or is reinjected, the latest user message already present in the DOM is treated as historical and is never executed as a newly observed operator command. SPA navigation to another conversation establishes a new user-message baseline for that conversation. Only a new user-authored operator marker observed after the active content script/baseline may mutate Bridge state.

A privileged Rebind uses a new `bindingRevision` and still blocks old/pre-rebind controls until the new bootstrap establishes the new baseline.

On every wake, the planner must:

1. trust the Bridge envelope and planner-scope policy as the conversation's authorization boundary;
2. for `repository` scope, inspect and act only on the bound repository;
3. for `multirepo` scope, resolve every target from the current runtime catalog and use that target's repository identity, execution state and canonical binding;
4. never substitute an unlisted repository or guessed binding for a catalog target;
5. avoid queueing a second task for the same target/goal while its current task is running;
6. inspect the exact terminal result before deciding the next bounded action;
7. pause when the required target is outside the authorized scope/catalog or requires unavailable authority;
8. keep no-change wake turns terse.

A conversation still needs a stated active goal. Planner scope defines where that goal may act; it does not invent work.

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

Local execution is queued by committing a new unique task file to the **target repository's** `agent-control` branch. Never hand-edit the daemon's local control clone.

## Choose GitHub or local execution

The planner may read and edit any repository allowed by the current planner scope through an available GitHub tool with the required permissions. Use this path for bounded source, configuration or documentation changes when review of the exact diff and relevant CI checks can verify the result. A GitHub commit proves a change, not successful execution; report the exact commit and completed checks.

Use Local Agent when the action needs command execution on the Mac, local build/test tools, device access or other machine-specific evidence and the target repository is execution-enabled. A hybrid flow may commit through GitHub and then queue a read-only verification task for that exact source SHA. Check the target repository's active task before editing the same branch while a local task is modifying it. Follow the target repository's own branch policy.

Every local task still requires a unique immutable id, the **target repository's exact `agent_binding`**, explicit `resources` and bounded execution. Direct GitHub edits do not require an artificial executor task merely to record that they happened. A multirepo conversation's own binding must never be copied into a task for a different target repository. The `local-agent` catalog entry remains unavailable for Local Agent self-execution; infrastructure source edits follow its release policy.

## Autonomous turn algorithm

For every bridge wake:

1. Parse and retain `LA_AGENT`, `LA_REPO`, `LA_REPOSITORY` and `LA_CHAT` plus the planner-scope policy supplied by Bridge.
2. Resolve the repository needed for the next action: the bound repository for normal scope, or one exact runtime-catalog target for multirepo scope. Never derive target identity from conversation history.
3. Read that target repository's current `.agent/status/daemon.json` and exact run/result evidence when local execution is relevant.
4. If the relevant target task is active and healthy, queue nothing else for that goal. If exact live evidence already proves that the active task cannot achieve its intended outcome, publish one repository-scoped `cancel_task` request for that exact task id instead of waiting for its timeout; then wait for the terminal cancellation/result evidence before replacing it.
5. If a terminal result exists, inspect its exact digest/result/command evidence.
6. Choose direct GitHub work or local execution using the rules above. If local execution is needed, create one new bounded task with a unique id and exactly the **target repository's** canonical `agent_binding`.
7. If the task fails deterministically, diagnose the evidence and create a new task only when the failure supports a specific fix. Never replay or mutate the old payload.
8. If the required repository is outside the authorized scope/catalog, use `PAUSE`; a normal repository-scoped conversation may explicitly Rebind, while multirepo work across listed targets must not Rebind merely to change targets.
9. If the goal is complete with relevant exact-commit CI or terminal local execution evidence, use `STOP`.
10. Otherwise use a suitable one-shot `NEXT` or allow normal pacing to resume.

The planner loop is sequential per active conversation goal, not globally serial. Independent repositories may proceed concurrently; `local_agent/supervisor/orchestrator.py` owns repository/resource concurrency.

## Active-task cancellation

`cancel_task` already exists as executor control; it is not a Chat Bridge UI shortcut. The planner may publish it only in the exact **target repository** that owns the active task and only for the exact task id supported by current run/status evidence:

```json
{
  "id": "cancel-<unique-id>",
  "action": "cancel_task",
  "task_id": "<exact-active-task-id>"
}
```

Use cancellation when current evidence makes failure unavoidable or proves that the task's premise is wrong, not merely because a task is taking longer than expected. An accepted active cancellation is owned by the worker executing that exact repository/task. Do not queue a replacement until the remote ACK and terminal task evidence establish what happened. Direct task cancellation is deliberately not part of the Browser Bridge LAB command plane; adding it would require a separate trusted repository-write transport.

## Task contract

Every Local Agent task must include the exact canonical `agent_binding` of its target executable repository:

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

For a normal repository-scoped conversation, the target binding equals the conversation binding. For a multirepo conversation, it normally differs whenever work targets another repository. `resources` remains mandatory and follows `docs/OPERATIONS.md`. Task ids/payloads are immutable within a repository. A new continuation uses a new id. The planner must never consider queueing itself proof of success; terminal result evidence is authoritative.

## Evidence order

For local execution, use evidence in this order:

1. terminal result for exact target repository + task id/digest;
2. live run/progress for the exact attempt;
3. current target-repository daemon status;
4. source/diff/test evidence referenced by the result;
5. planner analysis.

Binding failures are terminal safety evidence, not retry candidates with altered routing. Correct the target repository/catalog/control configuration or explicitly change the conversation binding when its planner scope itself is wrong; never bypass the target binding because a multirepo conversation exists.

## Post-queue liveness

Do not use 30-second polling for healthy executor work. After queueing, use one early autonomous re-check no sooner than about two minutes when immediate claim/failure evidence matters:

```text
[LAB:NEXT=2m]
```

Once execution is visibly healthy, choose pacing from evidence. Multi-minute builds and test suites should normally use 5-10 minute `NEXT` intervals, or a longer evidence-based delay when their expected duration is known. Shorter protocol values such as an explicit `[LAB:NEXT=30s]` remain accepted for operator/emergency compatibility, but they are not the autonomous healthy-task polling policy.

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

These commands return a Bridge-generated user message beginning with `[LA_BRIDGE_FEEDBACK]`. That message is **read-only local evidence**, not operator approval. `HELP` exposes the live installed command catalog. `DEBUG` reports local Bridge protocol/runtime/conversation evidence. Global `CHATS` and cross-chat `CHAT=<id>` inspection are available only when the current conversation is bound to the non-executing `local-agent` infrastructure binding; ordinary project chats are current-chat-only.

Assistant Bridge-local maintenance commands:

```text
[LAB:RELOAD=CONTENT]
[LAB:RELOAD=BRIDGE]
[LAB:RESTART=WORKER]
```

`RESTART=WORKER` is an alias for Bridge runtime/extension reload. It must never be interpreted as permission to restart the Local Agent supervisor. `RELOAD=CONTENT` refreshes only the exact current ChatGPT tab through the worker-owned dispose/inject/re-probe path.

Existing assistant scheduling controls remain:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
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

The assistant parser rejects `LAB:OP:*`. The operator scanner reads only the latest `data-message-author-role="user"` DOM message and the worker independently requires the same extension id, top frame and exact normalized conversation URL. `OP:ADD` resolves one exact repository id from the runtime catalog and creates the current chat disabled; it never guesses or implicitly rebinds. To change an existing conversation binding, the operator removes the current chat and explicitly adds it with the desired repository id. Multirepo target changes are not conversation-binding changes.

Already executed operator controls are persistently deduplicated in a bounded cache. Separately, the latest user message present when content protocol v5 activates/reinjects is baseline-only and is not executed; SPA navigation establishes a new baseline before scanning the destination conversation. These rules prevent install/reload/reinjection/navigation from replaying historical `LAB:OP:*` mutations.

A bridge control is accepted only when the final marker/suffix satisfies the strict syntax in `chat_bridge/README.md`. Compatibility forms using `LOCAL_AGENT_BRIDGE:` remain accepted for the assistant namespace. Only the last candidate marker is considered; malformed final candidates do not fall back to earlier markers.

Assistant scheduling semantics remain:

- `STOP`: disable this conversation and clear its interval override.
- `PAUSE`: disable this conversation while preserving its interval override.
- `RESUME`: re-enable this conversation; it does not change its binding.
- `NEXT=<duration>`: set `enabled=true` and arm/re-arm one conversation for a one-shot wake; the compatibility protocol accepts 30 seconds through 24 hours. Autonomous healthy-task polling follows the stricter pacing policy above and should not use less than two minutes.
- `INTERVAL=<minutes>`: set a persistent conversation pacing override.
- `INTERVAL=AUTO`: return to configured runtime pacing.

Per-chat operator settings are ordinary conversation state rather than a permanent operator lock. A later assistant scheduling control may overwrite the chat's manual pause/enabled state, next-wake timing or interval override. The global Bridge **Master** switch remains operator-only and is not mutable through assistant-safe LAB controls. No assistant marker can change repository binding.

## Completion and pause policy

Stop only when the requested outcome is supported by execution evidence. Executor `idle` means capacity is free; it does not create new scope.

Pause rather than guess when progress requires user action, external approval, unavailable credentials/hardware, a materially unresolved product choice, or a repository outside the conversation's authorized planner scope/current validated catalog. A multirepo conversation does not pause merely because the next valid target is a different listed repository.

Cancel an active task instead of passively waiting for its timeout only when exact current evidence already proves that the task cannot produce the intended result. Cancellation is a bounded executor action, not a substitute for impatience or ordinary progress polling.

## Required end-to-end validation for binding and planner scope

A binding/planner-scope rollout is complete only after all of these are demonstrated:

1. schema-3 runtime/catalog loads and a newly configured conversation stores one exact immutable binding;
2. normal edits cannot change that conversation's repository/binding;
3. a privileged binding revision change forces bootstrap and rejects old-revision controls;
4. an unbound/migrated conversation has no scheduled wake;
5. normal `planner_scope=repository` still emits single-repository policy and requires Rebind for another repository;
6. explicit `planner_scope=multirepo` permits work only across current runtime-catalog repositories without Rebind;
7. unknown planner scopes fail closed and execution-disabled bindings cannot advertise multirepo scope;
8. a multirepo target task uses the target repository's canonical binding rather than the conversation binding;
9. a task with the correct target binding executes and publishes terminal evidence;
10. a task with a missing binding is terminally rejected before claim/command execution;
11. a task with another repository's binding is terminally rejected before claim/command execution;
12. registry/control binding mismatch blocks repository admission;
13. the serial fallback preserves the same executor binding enforcement;
14. active `cancel_task` is observed through a remote-grounded ACK and terminates the targeted active task;
15. global `disable` prevents admission and can terminate active execution according to the emergency-control contract;
16. two conversations retain independent alarms/control state and cannot alter each other's binding through assistant controls;
17. assistant controls can overwrite operator-set per-chat pause/interval/timing state, but cannot change the global Bridge Master switch; Master-off suspends alarms without erasing per-chat desired timing;
18. assistant LAB controls cannot execute `LAB:OP:*` mutations;
19. content activation/reinjection and SPA navigation do not replay a historical user-authored operator marker;
20. a `local-agent` infrastructure conversation may inspect global Bridge chat routing metadata while a normal project-bound conversation remains current-chat-only.

Canonical executor and rollout rules remain in `AGENTS.md`, `docs/HOST_OPS_MULTIREPO.md` and `docs/OPERATIONS.md`.

## Delivery behavior in Bridge 0.5

Chat Bridge 0.5.6 uses **content protocol v5**. `CONTENT_PROTOCOL_VERSION` is owned only by `control_protocol.js`; content, worker, popup and tests consume that one value. Advancing v4 -> v5 is deliberate because 0.5.6 changes content behavior: a 0.5.6 worker must distinguish and replace already-open 0.5.5/v4 tabs.

The worker owns content activation for both scheduled delivery and popup onboarding. A missing or mismatched reachable content script is replaced without requiring a normal ChatGPT page reload: the worker disposes the current Bridge listener/timers and the actual exhaustion guard, injects `control_protocol.js`, `content_retry.js`, `content.js`, `dom_contract.js` and `exhaustion_guard.js`, then re-probes both content protocol and guard readiness. Popup code does not maintain a second protocol constant or its own `chrome.scripting.executeScript` policy.

The content script checks the exact conversation URL, protects operator drafts, authorizes normal wake delivery immediately before submission, and attempts to confirm the exact new user message in the DOM. Concurrent sends for the same conversation are rejected by an in-memory `delivery_in_progress` guard. Diagnostic `[LA_BRIDGE_FEEDBACK]` delivery remains local to the exact conversation and does not confer operator authority.

If Bridge inserted an exact wake but ChatGPT did not expose a usable Send button in time, the exact Bridge-owned prompt is left visible instead of being erased. If submission was attempted but the user-message DOM confirmation is missing, the exact retained prompt is also left alone. On a later run, Bridge may reuse a non-empty composer only when the previous conversation status is one of these recovery states **and** the composer text is byte-for-byte identical to the current Bridge prompt. Any operator edit, extra whitespace or unrelated draft fails closed as `composer_not_empty`/`composer_changed` and is never submitted automatically.

There is deliberately **no durable ambiguous-delivery journal**. If submission occurred but the exact DOM insertion/reply cannot be confirmed within the bounded observation window, Bridge records `delivery_unconfirmed` as diagnostic status only. It does not:

- pause or disable the conversation;
- create `pendingDelivery`;
- clear the next schedule because of uncertainty;
- block `STOP`, `PAUSE`, `RESUME`, `NEXT` or `INTERVAL`;
- require a manual resolution decision;
- block removal.

This intentionally accepts a small duplicate-send risk after lost confirmation in exchange for preventing transport uncertainty from deadlocking normal chat operation. Only a send that is currently in progress is protected; the guard is in memory and is gone after completion or service-worker restart.

Assistant control scanning is non-terminal on transient worker/message errors. The same unchanged assistant control is retried with bounded 5-30 second backoff until it is accepted or deterministically classified stale; there is no three-attempt permanent give-up that requires a page reload to reset.

Old schema-v3 `pendingDelivery` state is removed during normalization, and legacy `delivery_uncertain` status becomes non-blocking `delivery_unconfirmed`.

Browser fixture tests verify DOM submission, control/binding behavior, v4 -> v5 stale-content replacement, non-blocking retained-prompt recovery, operator replay baselining and worker restart in an isolated Chromium profile. They do not prove the current live ChatGPT DOM or the operator's currently loaded extension version.
