# GitHub-backed Chat Bridge control plane

## Status

This is the canonical scheduling/control contract for Chat Bridge `0.8.2`. GitHub desired state owns managed-chat pacing; Chat Bridge owns browser transport and browser-native Conversation Fabric; repository execution authorization remains exclusively at executable `.agent/tasks`.

Normal `STATUS`, `PAUSE`, `RESUME`, `NEXT` and `INTERVAL` operations for a managed conversation are not transported by assistant scheduling text. GitHub desired state in `chat_bridge/runtime.json` on `chat-bridge-state` is authoritative.

Conversation Fabric uses a dedicated `LOCAL_AGENT_CF` assistant control only for child delegation/collection. It does not own pacing. When a campaign needs another observation, the parent updates its GitHub `conversation_controls` record with a new `control_generation` and bounded `next_wake_at`.

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

Production topology is one normal/daily Chrome profile acting as the executor for a managed conversation. Parent and Conversation Fabric child tabs are ordinary tabs in that same session.

A second profile may exist only for bounded diagnostics/test work when it cannot execute the same managed conversation. It is not a second production executor. Conversation Fabric acceptance must not use an isolated `chat-bridge-cft` profile, another production Chrome process, CDP as a second production control plane, cookie migration or a separate login/Cloudflare path.

## Conversation Fabric interaction

Chat Bridge `0.8.2` adds browser-native child reasoning without changing scheduling authority:

```text
managed parent
  -> LOCAL_AGENT_CF delegate/collect control
  -> Chat Bridge service worker
  -> existing worker_spawn.js tab ownership primitives
  -> reasoning-only child tabs
  -> stable result capture / owned-tab cleanup
```

Only the exact managed parent may start/collect a campaign. Children cannot recursively gain parent authority. Campaign state is browser-session scoped and does not authorize repository execution.

If a campaign is still pending, Bridge returns a parent feedback prompt instructing the planner to schedule a GitHub-managed future wake. The planner must update the exact `conversation_controls` record and increment `control_generation`; it must not use LAB `NEXT`/`INTERVAL` markers for normal Conversation Fabric pacing.

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

Visible assistant generation blocks overlapping submission. Operator composer edits are never overwritten. Unconfirmed delivery does not cause speculative repeat clicks.

## Historical live evidence

Earlier 2026-09-30 and 2026-10-01 production proofs established GitHub-managed pause/resume/NEXT discovery and wake delivery in normal daily Chrome. Those proofs remain historical pacing evidence; they predate browser-native Conversation Fabric `0.8.2` and do not by themselves satisfy the new primary-Chrome child acceptance.

## Source of truth

- desired-state model: `chat_bridge/github_control_model.js`;
- reconciliation: `chat_bridge/worker_github_control.js`;
- legacy authority gate: `chat_bridge/worker_github_legacy_gate.js`;
- scheduler: `chat_bridge/worker_schedule.js`;
- normal delivery: `chat_bridge/content.js` + worker delivery modules;
- Conversation Fabric: `chat_bridge/conversation_fabric_protocol.js`, `chat_bridge/conversation_fabric_content.js`, `chat_bridge/worker_conversation_fabric.js`;
- planner flow: `docs/AUTONOMOUS_CHAT_LOOP.md`;
- release invariants: `docs/GOLDEN_STANDARD.md`.
