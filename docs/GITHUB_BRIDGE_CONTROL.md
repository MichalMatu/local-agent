# GitHub-backed Chat Bridge control plane

## Status

This is the canonical conversation scheduling/control contract for Chat Bridge 0.6.2 / Local Agent 4.19.11. It preserves the GitHub control-plane hardening from PR #118 and adds the terminal-safety repair verified by PR #122.

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

`control_generation` is a positive monotonically increasing integer within one binding revision. Every schedule mutation increments it. `STATUS` is a read and does not increment it. Once a generation has been applied, its desired-state payload is immutable: rewriting `enabled`, interval, deadline or update evidence under the same generation fails closed instead of being treated as local drift. A lower remote generation is a rollback and cannot replace the applied state.

A disabled control must have `next_wake_at=null`. A one-shot deadline must not precede `updated_at` and must be no more than 24 hours after `updated_at`. This keeps GitHub NEXT semantics bounded by the same maximum horizon as the compatibility protocol.

## Operations

For a managed chat:

- `STATUS`: read the exact `conversation_controls` record from GitHub;
- `PAUSE`: increment generation, set `enabled=false`, `next_wake_at=null`;
- `RESUME`: increment generation, set `enabled=true`, `next_wake_at=null`;
- `NEXT`: increment generation, set `enabled=true`, set exact future `next_wake_at`;
- `INTERVAL`: increment generation and set `interval_minutes` or `null` for runtime default.

The global Bridge Master switch is never changed by a conversation desired-state record.

## Reconciliation and idempotence

Applied GitHub state is tracked by `(bindingRevision, controlGeneration, localGeneration)` plus a canonical signature of the applied desired-state payload.

- A higher GitHub generation applies new desired state.
- Re-reading an already-correct generation does not re-arm an unchanged one-shot wake.
- A same-generation remote payload rewrite is rejected; the generation must be incremented for every desired-state mutation.
- A lower remote generation is ignored and cached applied ownership remains authoritative locally.
- A local popup/legacy pacing mutation changes local generation and is repaired on the next reconcile.
- A consumed/past one-shot wake falls back to normal interval scheduling instead of being replayed forever, including when a fresh/cold Chrome profile first observes that already-expired generation.
- Rebind creates a new binding revision and therefore an independent generation space.
- Reconciliation is serialized within one MV3 worker instance so concurrent activation/popup/alarm paths cannot apply the same remote generation twice.
- Control-boundary reconciliation bypasses both the ordinary 30-second runtime cache and any older in-flight configuration request. Fetch sequence ordering prevents an older request from overwriting a newer control-boundary result in the cache.

Once a matching GitHub generation has been applied, schedule ownership is sticky for that binding revision. Network failure, malformed remote state, a stale rollback, a same-generation rewrite, or a temporarily missing exact control record preserves the last applied GitHub ownership instead of silently handing pacing authority back to DOM/local controls. Explicit Rebind creates a new binding revision. Explicit Remove deletes the local conversation and clears its applied-ownership journal entry so a later re-add starts cleanly.

Malformed controls, duplicate conversation records, stale binding revisions, invalid timestamps/ranges or identity mismatches fail closed.

## Discovery lifecycle

Every Manifest V3 service-worker activation ensures a dedicated one-minute GitHub-control alarm exists. `onInstalled` and `onStartup` perform the same idempotent initialization. This includes manual Reload of an unpacked extension.

The alarm only reads the existing public remote runtime URL. No GitHub credential is stored in the extension and the extension never writes to GitHub.

The worker also reconciles GitHub desired state before popup state reads, manual `Run now` and normal scheduled wake delivery.

A temporary runtime/network failure leaves the last applied state unchanged. Once a conversation has GitHub ownership, network failure or temporary record omission does not silently hand pacing authority back to DOM controls.

`chrome.alarms` is a discovery/scheduling primitive, not a real-time clock. Chrome may delay an alarm, so the one-minute poll is a bounded discovery cadence rather than an exact one-minute delivery guarantee.

## Chrome-profile ownership boundary

Current 0.6.2 state, alarms, applied-generation journal and in-flight delivery guard are all profile-local. Therefore two independent Chrome profiles configured for the same managed conversation can both accept the same desired generation and both attempt the same wake.

Until a reviewed shared executor/lease contract exists, one managed conversation must have only one active Chrome-profile executor. Exactly-once delivery across two independent profiles cannot be guaranteed by a local-only dedupe flag. A future design should use an explicit desired-state executor/profile owner or another shared writable lease rather than renderer heuristics.

The supported production topology is therefore one normal/daily Chrome profile acting as the executor. A second profile may be used for Chrome Dev or bounded diagnostics, including while it is open at the same time, provided it is not also able to execute the same managed conversation. In practice, keep that conversation unconfigured/removed in the diagnostic profile or keep the diagnostic profile's Bridge Master off except during an intentional bounded test. A diagnostic profile is not a second production executor.

This limitation is separate from stale one-shot replay: the hardening prevents a fresh profile from immediately replaying an already-expired NEXT, but it cannot arbitrate two profiles that concurrently own the same still-future generation.

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

return `github_control_managed` and do not mutate scheduler state when an exact or previously-applied GitHub control owns the conversation.

For a managed conversation, assistant `[LAB:STATUS]` is also a compatibility no-op; it must not inject a local DOM feedback status that competes with GitHub desired state. Read the exact `conversation_controls` record instead.

The following remain explicit migration/maintenance surfaces until separately moved to GitHub state:

- binding: `ADD`, `REBIND`, `REMOVE`;
- inspection/diagnostics not replaced by the desired-state read;
- `RELOAD=CONTENT`, `RELOAD=BRIDGE`, `RESTART=WORKER`.

They must not be used for ordinary schedule/status operations.

## Popup ownership

The popup remains the local operator surface for binding/onboarding, global Master, manual `Run now`, removal and diagnostics. When GitHub owns a conversation, its per-conversation enable switch and interval field are rendered read-only and labelled `GitHub managed`. During a remote outage, missing-record publication, rollback or same-generation conflict, the popup shows the last applied local state rather than presenting stale remote values as authoritative. Worker-side mutation guards enforce the same ownership boundary even if UI state is stale.

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

The hardening does not add a speculative second click or automatic resubmit when the exact user turn is unconfirmed. `delivery_unconfirmed` remains diagnostic until a reproducible browser root cause justifies a narrower change.

## Live proof

On 2026-09-30 the daily-Chrome conversation `chat-e8ad8275` completed the original managed flow:

1. generation 1 `PAUSE`;
2. generation 2 `RESUME`;
3. generation 3 `NEXT` at an exact two-minute deadline;
4. Bridge 0.6.0 discovered the new state and submitted the wake to the correct chat;
5. the wake returned with the immutable `host-ops` binding envelope;
6. generation 4 returned the chat to `PAUSED`.

A later 05:02 run on `chat-be9defd7` proved the scheduled delivery path for the extension build then loaded, but was deliberately not counted as hardening-specific proof after the popup evidence showed that Chrome most likely still had the earlier runtime loaded.

The definitive merged-hardening proof used the same active conversation `chat-be9defd7`, bound to `MichalMatu/local-agent` at binding revision 1:

1. the local checkout was confirmed at current `main` `39aecf90efef1ef03b5facdab837ba8366eaeb85` and the unpacked Chat Bridge 0.6.0 extension was reloaded in the normal/daily Chrome profile;
2. generation 4 armed one exact `NEXT` for `2026-09-30T15:09:00+02:00`;
3. without `Run now` or LAB scheduling, the automatic wake arrived at approximately `15:09:15+02:00` with the exact `chat-be9defd7` / `local-agent` binding envelope;
4. generation 5 immediately returned the conversation to `PAUSED`, with `enabled=false` and `next_wake_at=null`;
5. the popup then visibly showed `GitHub managed`, `github_control_paused`, `Paused`, a `GitHub interval` field, and disabled per-conversation schedule controls.

This closes the hardening-specific production field gate on the exact merged runtime. The final desired state for the active test conversation is intentionally `enabled=false`, `next_wake_at=null`.

## Checkpoint live proof

On 2026-10-01 the operator successfully exercised the GitHub-managed wake path with a short one-minute interval using the checkpoint Bridge build. The automatic wake occurred without using the legacy LAB scheduling path, and the managed conversation was returned to the canonical paused state: `enabled=false`, `next_wake_at=null`. Exact conversation/control identifiers are intentionally omitted from public documentation.

## Source of truth

- control schema/model: `chat_bridge/github_control_model.js`;
- reconciliation: `chat_bridge/worker_github_control.js`;
- legacy authority gate: `chat_bridge/worker_github_legacy_gate.js`;
- runtime parser: `chat_bridge/worker_runtime.js`;
- scheduler: `chat_bridge/worker_schedule.js`;
- delivery: `chat_bridge/content.js` + worker delivery modules;
- planner flow: `docs/AUTONOMOUS_CHAT_LOOP.md`;
- release invariants: `docs/GOLDEN_STANDARD.md`.
