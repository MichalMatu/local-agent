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

`control_generation` is a positive monotonically increasing integer for that conversation. A higher generation applies new desired state exactly once. Re-reading the same generation does not re-arm an already-correct one-shot wake. If legacy DOM controls or the popup drift `enabled` or `interval_minutes`, the same GitHub generation repairs that drift back to the authoritative desired state.

`enabled=false` clears the conversation alarm. `enabled=true` schedules `next_wake_at` when it is present; otherwise it uses `interval_minutes`, or the runtime default interval when that field is null. A past one-shot deadline is never replayed indefinitely: drift recovery after that deadline falls back to the normal interval.

`updated_at` and `next_wake_at` are offset-aware ISO timestamps. `next_wake_at` may be null. `interval_minutes` may be null or use the existing Bridge interval bounds.

## Discovery lifecycle

Chrome creates a dedicated one-minute GitHub-control alarm during extension install/startup. Chrome alarms survive Manifest V3 service-worker suspension, so a remotely paused conversation can later discover a GitHub `RESUME` even when it has no conversation wake alarm of its own.

The GitHub-control alarm only fetches the existing public remote runtime URL. The extension does not contain a GitHub token and does not write to GitHub.

The worker also reconciles remote desired state before popup state reads, manual `Run now`, and ordinary scheduled wake delivery. Runtime fetch failure leaves the last local state unchanged and fails closed.

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

Assistant/user LAB schedule controls may remain temporarily as a compatibility fallback during migration, but they are no longer authoritative for a conversation managed by `conversation_controls`. The next reconciliation repairs any local schedule drift back to GitHub desired state.

The target architecture removes assistant-side DOM parsing from the normal pacing path entirely. ChatGPT DOM changes must not be able to change whether GitHub says a conversation is paused, resumed, or scheduled for a specific wake.

## Security and failure properties

- no GitHub credential is shipped in the extension;
- remote desired state is read from the already configured public runtime endpoint;
- repository/binding identity is validated twice: against the runtime catalog and against local conversation binding state;
- stale binding revisions fail closed;
- stale control generations are ignored;
- duplicate conversation-control records are rejected;
- malformed timestamps, ranges, identities, or booleans make remote runtime validation fail closed;
- remote runtime unavailability does not silently substitute another control source;
- the conversation control plane cannot change global Master.

## Rollout

1. Ship/test the 0.6.0 worker while `conversation_controls` is absent or empty.
2. Add one exact conversation desired-state record on `chat-bridge-state` with an incrementing generation.
3. Verify PAUSE, RESUME, one-shot NEXT and interval changes from GitHub without assistant LAB markers.
4. End the live validation with the conversation paused.
5. After stable field evidence, deprecate assistant DOM schedule controls for GitHub-managed conversations.
