# GitHub-backed Chat Bridge control plane

## Goal

Conversation pacing must not depend on parsing assistant text from the ChatGPT DOM. The DOM remains a transport surface for observing generation state and submitting a wake prompt, but GitHub remote runtime state is the authoritative control plane for conversation scheduling.

Chat Bridge 0.6.0 keeps remote runtime `schema_version: 3` for backward compatibility and adds an optional top-level `conversation_controls` array. Older Bridge builds ignore this additional field. A 0.6.0 worker validates and reconciles it.

## Desired-state record

One controlled conversation has one record:

```json
{
  "conversation_id": "chat-e8ad8275",
  "repository_id": "host-ops",
  "repository": "MichalMatu/host-ops",
  "agent_binding": "16d688b6-b0ef-4905-a5bd-24e59c99cfb4",
  "binding_revision": 1,
  "control_generation": 12,
  "enabled": false,
  "interval_minutes": 5,
  "next_wake_at": null,
  "updated_at": "2026-09-30T00:40:00+02:00"
}
```

`conversation_id`, repository identity, canonical `agent_binding`, and `binding_revision` must match the locally configured conversation exactly. The repository tuple must also exist in the current validated runtime agent catalog. Mismatches fail closed and do not mutate local state.

`control_generation` is a positive monotonically increasing integer within one binding revision. A higher generation applies new desired state exactly once. Re-reading the same generation does not re-arm an already-correct one-shot wake. Applied acknowledgements are scoped by binding revision and local conversation generation, so an explicit rebind gets an independent generation space and any local pacing mutation is detectable.

`enabled=false` clears the conversation alarm. `enabled=true` schedules `next_wake_at` when it is present; otherwise it uses `interval_minutes`, or the runtime default interval when that field is null. A past one-shot deadline is never replayed indefinitely: drift recovery after that deadline falls back to the normal interval.

`updated_at` and `next_wake_at` are offset-aware ISO timestamps. `next_wake_at` may be null. `interval_minutes` may be null or use the existing Bridge interval bounds.

## Discovery lifecycle

Chrome creates a dedicated one-minute GitHub-control alarm during extension install/startup. Chrome alarms survive Manifest V3 service-worker suspension, so a remotely paused conversation can later discover a GitHub `RESUME` even when it has no conversation wake alarm of its own.

The GitHub-control alarm only fetches the existing public remote runtime URL. The extension does not contain a GitHub token and does not write to GitHub.

The worker also reconciles remote desired state before popup state reads, manual `Run now`, and ordinary scheduled wake delivery. Runtime fetch failure leaves the last local state unchanged and fails closed. If a matching GitHub control was already applied, temporary runtime/network failure does not hand schedule ownership back to DOM controls.

## Control ownership

For conversations present in `conversation_controls`, GitHub is authoritative for schedule state:

- pause: increment `control_generation`, set `enabled=false`, `next_wake_at=null`;
- resume: increment generation, set `enabled=true`, `next_wake_at=null`;
- next: increment generation, set `enabled=true`, set exact future `next_wake_at`;
- interval: increment generation and set `interval_minutes` or null;
- status: read this desired-state record directly from GitHub; no assistant DOM marker is required.

The global Master switch remains local operator state and is never changed by a conversation control record.

Binding mutations (`ADD`, `REBIND`, `REMOVE`) are intentionally outside this first desired-state contract. Existing explicit binding paths remain in place until a separate GitHub binding-control design is reviewed.

## Legacy LAB compatibility

For a GitHub-managed conversation, assistant schedule controls (`STOP`, `PAUSE`, `RESUME`, `NEXT`, `INTERVAL`) and user `OP:ENABLE` / `OP:DISABLE` / `OP:INTERVAL` are recognized only so the scanner can terminate/dedupe them. They return `github_control_managed` and do not mutate scheduler state. Inspection, binding and Bridge-maintenance controls remain available during migration.

A popup or older local build can still mutate local pacing state temporarily. The applied ACK stores `(bindingRevision, controlGeneration, localGeneration)`, so the next reconciliation detects that generation drift and restores GitHub desired state. A schedule-only legacy `NEXT` is therefore detected even when `enabled` and `interval_minutes` themselves did not change.

The target architecture removes assistant-side DOM parsing from the normal pacing path entirely. ChatGPT DOM changes must not be able to change whether GitHub says a conversation is paused, resumed, or scheduled for a specific wake.

## Security and failure properties

- no GitHub credential is shipped in the extension;
- remote desired state is read from the already configured public runtime endpoint;
- repository/binding identity is validated twice: against the runtime catalog and against local conversation binding state;
- stale binding revisions fail closed;
- stale control generations are ignored;
- applied generations are binding-revision scoped;
- duplicate conversation-control records are rejected;
- malformed timestamps, ranges, identities, or booleans make remote runtime validation fail closed;
- remote runtime unavailability does not silently substitute another control source after GitHub ownership has been established;
- the conversation control plane cannot change global Master.

## Rollout

1. Ship/test the 0.6.0 worker while `conversation_controls` is absent or empty.
2. Add one exact conversation desired-state record on `chat-bridge-state` with an incrementing generation.
3. Verify PAUSE, RESUME, one-shot NEXT and interval changes from GitHub without assistant LAB markers.
4. End the live validation with the conversation paused.
5. After stable field evidence, deprecate assistant DOM schedule controls for GitHub-managed conversations.
