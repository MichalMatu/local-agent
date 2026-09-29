# GitHub-backed Chat Bridge control plane

## Status

This is the canonical conversation scheduling/control contract for Chat Bridge 0.6.0 / Local Agent 4.19.9.

Normal `STATUS`, `PAUSE`, `RESUME`, `NEXT` and `INTERVAL` operations for a managed conversation are no longer transported by assistant text in the ChatGPT DOM. GitHub desired state in `chat_bridge/runtime.json` on `chat-bridge-state` is authoritative.

The ChatGPT DOM remains a delivery surface only: generation-state checks, exact-conversation wake insertion/submission, submitted-user confirmation, terminal-error recovery and explicit migration/maintenance controls.

## Desired-state record

`runtime.json` keeps `schema_version: 3` for backward compatibility and adds optional `conversation_controls`:

```json
{
  "conversation_id": "chat-e8ad8275",
  "repository_id": "host-ops",
  "repository": "MichalMatu/host-ops",
  "agent_binding": "16d688b6-b0ef-4905-a5bd-24e59c99cfb4",
  "binding_revision": 1,
  "control_generation": 4,
  "enabled": false,
  "interval_minutes": 5,
  "next_wake_at": null,
  "updated_at": "2026-09-30T01:41:54+02:00"
}
```

The worker accepts a control only when conversation id, repository id/name, canonical binding and binding revision match both the validated runtime catalog and the locally configured conversation.

`control_generation` is a positive monotonically increasing integer within one binding revision. Every schedule mutation increments it. `STATUS` is a read and does not increment it.

## Operations

For a managed chat:

- `STATUS`: read the exact `conversation_controls` record from GitHub;
- `PAUSE`: increment generation, set `enabled=false`, `next_wake_at=null`;
- `RESUME`: increment generation, set `enabled=true`, `next_wake_at=null`;
- `NEXT`: increment generation, set `enabled=true`, set exact future `next_wake_at`;
- `INTERVAL`: increment generation and set `interval_minutes` or `null` for runtime default.

The global Bridge Master switch is never changed by a conversation desired-state record.

## Reconciliation and idempotence

Applied GitHub state is tracked by `(bindingRevision, controlGeneration, localGeneration)`.

- A higher GitHub generation applies new desired state.
- Re-reading an already-correct generation does not re-arm an unchanged one-shot wake.
- A local popup/legacy pacing mutation changes local generation and is repaired on the next reconcile.
- A consumed/past one-shot wake falls back to normal interval scheduling instead of being replayed forever.
- Rebind creates a new binding revision and therefore an independent generation space.

Malformed controls, duplicate conversation records, stale binding revisions, invalid timestamps/ranges or identity mismatches fail closed.

## Discovery lifecycle

Every Manifest V3 service-worker activation ensures a dedicated one-minute GitHub-control alarm exists. `onInstalled` and `onStartup` perform the same idempotent initialization. This includes manual Reload of an unpacked extension.

The alarm only reads the existing public remote runtime URL. No GitHub credential is stored in the extension and the extension never writes to GitHub.

The worker also reconciles GitHub desired state before popup state reads, manual `Run now` and normal scheduled wake delivery.

A temporary runtime/network failure leaves the last applied state unchanged. Once a conversation has GitHub ownership, network failure does not silently hand pacing authority back to DOM controls.

## Legacy LAB compatibility

The LAB parser remains for migration, diagnostics, binding and maintenance, but it is not the normal pacing transport for a GitHub-managed chat.

Assistant schedule controls:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:NEXT=...]
[LAB:INTERVAL=...]
```

and user pacing controls:

```text
[LAB:OP:ENABLE]
[LAB:OP:DISABLE]
[LAB:OP:INTERVAL=...]
```

return `github_control_managed` and do not mutate scheduler state when an exact GitHub control record owns the conversation.

The following remain explicit migration/maintenance surfaces until separately moved to GitHub state:

- binding: `ADD`, `REBIND`, `REMOVE`;
- inspection/diagnostics not replaced by the desired-state read;
- `RELOAD=CONTENT`, `RELOAD=BRIDGE`, `RESTART=WORKER`.

They must not be used for ordinary schedule/status operations.

## Wake delivery boundary

GitHub decides **when** the conversation is armed. Chrome still owns the browser action:

```text
GitHub desired state
  -> one-minute remote reconcile
  -> chrome.alarms conversation wake
  -> exact preferred ChatGPT tab/conversation
  -> write Bridge wake prompt
  -> re-resolve enabled Send button
  -> live DOM click (requestSubmit only fallback)
  -> confirm exact user turn
```

A visible ChatGPT Stop control blocks overlapping submission. Operator edits in the composer are never overwritten. Retained Bridge text may be reused only if it still exactly matches the Bridge-owned prompt.

## Live proof

On 2026-09-30 the daily-Chrome conversation `chat-e8ad8275` completed the full managed flow:

1. generation 1 `PAUSE`;
2. generation 2 `RESUME`;
3. generation 3 `NEXT` at an exact two-minute deadline;
4. Bridge 0.6.0 discovered the new state and submitted the wake to the correct chat;
5. the wake returned with the immutable `host-ops` binding envelope;
6. generation 4 returned the chat to `PAUSED`.

The final desired state is intentionally `enabled=false`, `next_wake_at=null`.

## Source of truth

- control schema/model: `chat_bridge/github_control_model.js`;
- reconciliation: `chat_bridge/worker_github_control.js`;
- legacy authority gate: `chat_bridge/worker_github_legacy_gate.js`;
- runtime parser: `chat_bridge/worker_runtime.js`;
- scheduler: `chat_bridge/worker_schedule.js`;
- delivery: `chat_bridge/content.js` + worker delivery modules;
- planner flow: `docs/AUTONOMOUS_CHAT_LOOP.md`;
- release invariants: `docs/GOLDEN_STANDARD.md`.
