# GitHub-backed Chat Bridge control plane

## Status

This is the canonical scheduling/control contract for Chat Bridge `0.8.14`. GitHub desired state owns managed-chat pacing; Chat Bridge owns browser transport and browser-native Conversation Fabric; repository execution authorization remains exclusively at executable `.agent/tasks` after canonical runtime-catalog admission.

Normal `STATUS`, `PAUSE`, `RESUME`, `NEXT` and `INTERVAL` operations for a managed conversation are not transported by assistant scheduling text. GitHub desired state in `chat_bridge/runtime.json` on `chat-bridge-state` is authoritative.

Conversation Fabric uses a dedicated `LOCAL_AGENT_CF` assistant control for delegation and bounded recovery/inspection. It does not own repository execution authority and does not replace GitHub conversation pacing.

## Desired-state record

`runtime.json` keeps `schema_version: 3` and optional `conversation_controls`:

```json
{
  "conversation_id": "chat-e8ad8275",
  "control_generation": 4,
  "enabled": false,
  "interval_minutes": 5,
  "next_wake_at": null,
  "updated_at": "2026-09-30T01:41:54+02:00"
}
```

The exact conversation id must match the locally configured managed conversation. Legacy repository/binding fields may remain in migrated records but are not scheduling ownership or repository execution authority.

`control_generation` is a positive monotonically increasing integer. Every desired-state schedule mutation increments it. Rewriting desired state under the same generation fails closed. Lower generations are stale rollbacks and cannot replace the applied state.

A disabled control must have `next_wake_at=null`. A one-shot deadline must not precede `updated_at` and remains bounded by the supported future horizon.

## Operations

For a managed chat:

- `STATUS`: read the exact GitHub `conversation_controls` record;
- `PAUSE`: increment generation, set `enabled=false`, `next_wake_at=null`;
- `RESUME`: increment generation, set `enabled=true`, `next_wake_at=null`;
- `NEXT`: increment generation, set `enabled=true`, set exact future `next_wake_at`;
- `INTERVAL`: increment generation and set `interval_minutes` or `null` for runtime default.

The global Bridge Master switch is independent manual operator state and is never changed by a conversation desired-state record.

## MVP: optional exact task-result wake (single active Chrome)

A GitHub-managed parent may opt into one task-completion wake hint by adding
`task_result_watch` **inside its exact `conversation_controls` record**:

```json
{
  "conversation_id": "chat-00000000",
  "control_generation": 2,
  "enabled": true,
  "interval_minutes": 10,
  "next_wake_at": null,
  "updated_at": "2026-10-10T07:00:00Z",
  "task_result_watch": {
    "repository_id": "local-agent",
    "task_id": "exact-unique-task-id"
  }
}
```

The sample ID is illustrative, not a registration instruction. Select the
actual repository from the canonical execution catalog and publish a legitimate
bound task before watching its result. The repository must also be an enabled
agent in the Bridge runtime catalog. This hint grants **no** execution right.
Each new/changed watch is a desired-state mutation and therefore requires a
strictly newer `control_generation`; same-generation rewrites are conflicts.

The existing one-minute GitHub-control alarm reads the exact task's bounded
public `agent-control/.agent/results/<task_id>.json` path. A missing result
is inert. An exact terminal `done`, `failed` or `cancelled` result advances
only the **ordinary conversation alarm** to the near future. It does not
call Send, bypass current Chrome/parent/composer checks, create a new alarm
owner, load task commands, or execute anything. Before changing the alarm,
it revalidates current parent enablement, Master, applied signed generation
and task identity, and records a bounded durable one-time claim.

If the result is unavailable/oversized/ambiguous or the watcher cannot safely
schedule, keep the ordinary 10-minute cadence as the fallback. A surviving
ambiguous one-time claim is never replayed automatically. Remove
`task_result_watch` and increment `control_generation` after the parent has
processed the result. No watcher is configured by default; the deployed
extension must be reloaded before this optional code can run.

For MVP the supported topology stays one operator-controlled Mac and one
active production Chrome session. No Android, additional production profile,
CDP transport, GitHub credential in the extension, or new scheduler is added.

## Reconciliation/idempotence

Applied GitHub state is tracked by chat identity, control generation, local generation and canonical desired-state signature.

- higher valid generation applies new desired state;
- re-reading an already-correct generation does not re-arm unchanged one-shot work;
- same-generation rewrites fail closed;
- lower generations are ignored;
- local popup/legacy pacing drift is repaired by the next reconcile;
- consumed/past one-shot wakes are not replayed forever;
- reconciliation is serialized within one MV3 worker instance;
- control-boundary reads bypass stale ordinary runtime cache state.

Once GitHub ownership is established, temporary network failure, malformed remote state, stale rollback, same-generation conflict or temporary record omission preserves the last applied ownership rather than silently handing pacing authority back to DOM/LAB controls.

## Browser ownership boundary

Production topology is one normal/daily Chrome profile acting as the browser executor for a managed conversation. Parent and Conversation Fabric child tabs are ordinary tabs in that same session.

A second profile may exist only for bounded diagnostics/test work when it cannot execute the same managed conversation. It is not a second production executor. Conversation Fabric acceptance must not use an isolated production profile, another production Chrome process, CDP as a second production control plane, cookie migration or a separate login/Cloudflare path.

## Conversation Fabric interaction

Chat Bridge `0.8.13` adds browser-native child reasoning without changing scheduling authority:

```text
managed parent
  -> LOCAL_AGENT_CF delegate
  -> Chat Bridge service worker
  -> existing worker_spawn.js tab ownership primitives
  -> reasoning-only child tabs
  -> stable result capture into durable campaign state
  -> owned-tab cleanup
  -> terminal parent feedback at most once
```

Only the exact managed parent may start/collect a campaign. Children cannot recursively gain parent authority. Campaign/result state is durable in `chrome.storage.local` and does not authorize repository execution.

The existing one-minute GitHub-control alarm performs the normal combined lifecycle: reconcile GitHub conversation controls, then poll active Conversation Fabric campaigns while the parent and Master are enabled. Parent-authored short wake scheduling is not required merely to keep observing an active campaign.

An explicit `collect` control is reserved for bounded recovery/inspection of already-submitted children. It must never replay or resubmit their bootstrap prompts.

## Conversation Fabric restart and delivery semantics

- Stable child results are durably saved before sibling completion or owned-tab cleanup.
- Service-worker restart/reload may clear session ownership. Reattachment is permitted only after the child page proves the exact transaction id, child-request digest, bootstrap digest and current child conversation URL. Tab id alone is insufficient.
- Ambiguous/pre-submit child submission fails closed rather than being blindly replayed.
- Transient observation failures remain pending and may recover on later polls.
- Terminal feedback uses a durable per-campaign delivery claim persisted before crossing the parent Send boundary.
- Definite no-send clears the claim; confirmed delivery marks it delivered; an ambiguous surviving claim is treated as consumed after restart to preserve at-most-once delivery.
- A new delegation for the same parent is rejected while an older terminal campaign still has undelivered feedback. This prevents stale terminal feedback from an obsolete campaign being replayed after a newer campaign becomes authoritative.
- The at-most-once rule intentionally prefers a potentially missed terminal notification after an ambiguous crash over duplicate terminal delivery.

## Legacy LAB compatibility

LAB parsing remains for migration, diagnostics, binding and maintenance compatibility. For a GitHub-managed conversation, assistant/user schedule controls are not the normal scheduling transport and do not supersede GitHub ownership.

Explicit binding/maintenance surfaces may remain until separately migrated, but they must not be used for ordinary status/pacing or Conversation Fabric campaign continuation.

## Wake delivery boundary

GitHub decides **when** the parent is armed. Chrome owns the browser action:

```text
GitHub desired state
  -> remote reconcile
  -> chrome.alarms parent wake
  -> exact preferred ChatGPT tab/conversation
  -> bounded prompt insertion
  -> live Send control
  -> exact submitted-user confirmation
```

Visible assistant generation blocks overlapping submission. Operator composer edits are never overwritten. Unconfirmed ordinary wake delivery does not cause speculative repeat clicks.

Conversation Fabric terminal delivery has the additional durable campaign-specific at-most-once claim described above; do not generalize that journal to ordinary wake delivery.

## Repository execution authority

Chat Bridge never turns transport identity into task authority. For any executable Local Agent work, the parent must resolve the actual repository through the canonical runtime catalog, require `execution_enabled=true`, and use the exact canonical target `agent_binding`. Registry/control agreement without a catalog match fails closed.

The current catalog enables `local-agent`; this is not a special bypass. Self-execution follows the same target binding, lease, resource and emergency-control gates as any other repository.

## Historical live evidence

Earlier 2026-09-30 and 2026-10-01 production proofs established GitHub-managed pause/resume/NEXT discovery and wake delivery in normal daily Chrome. Those proofs remain historical pacing evidence; browser-native Conversation Fabric acceptance must additionally cover durable campaign recovery and terminal at-most-once semantics.

## Source of truth

- desired-state model: `chat_bridge/github_control_model.js`;
- reconciliation: `chat_bridge/worker_github_control.js`;
- scheduler/alarm identity: `chat_bridge/worker_base.js` + `chat_bridge/worker_events.js`;
- normal delivery: `chat_bridge/content.js` + worker delivery modules;
- Conversation Fabric: `chat_bridge/conversation_fabric_protocol.js`, `chat_bridge/conversation_fabric_content.js`, `chat_bridge/worker_conversation_fabric.js`, recovery and terminal-delivery guard modules;
- planner flow: `docs/AUTONOMOUS_CHAT_LOOP.md`;
- release/runtime invariants: `docs/GOLDEN_STANDARD.md`.
