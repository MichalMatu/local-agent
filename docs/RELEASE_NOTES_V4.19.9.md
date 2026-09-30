# Local Agent 4.19.9

## Summary

Local Agent 4.19.9 promotes Chat Bridge 0.6.0 and moves normal conversation pacing/status control from assistant DOM markers to GitHub-backed desired state in `chat_bridge/runtime.json` on the `chat-bridge-state` branch.

The release keeps the existing repository/binding and wake-delivery model, but makes GitHub the authoritative source for `STATUS`, `PAUSE`, `RESUME`, `NEXT` and `INTERVAL` for managed conversations. The ChatGPT DOM remains necessary only for generation-state checks, wake prompt insertion/submission, delivery confirmation, terminal error recovery and explicit migration/maintenance controls.

## Why this release exists

The 4.19.3-4.19.8 series accumulated renderer-specific assistant-turn heuristics because ChatGPT changed how role metadata and grouped turns were exposed. Live inspection of a saved failing page showed that `data-conversation-role="assistant"` could be attached only to an accessibility label (`ChatGPT said:`) while the real assistant body was a sibling. This made assistant-side schedule markers an unnecessarily fragile control transport.

4.19.9 removes that dependency from the normal scheduling path rather than adding another DOM heuristic.

## GitHub-backed conversation control

`runtime.json` schema remains `3` for backward compatibility and gains the optional `conversation_controls` array. Each controlled conversation record carries:

- exact `conversation_id`;
- exact repository id/name and canonical `agent_binding`;
- exact `binding_revision`;
- monotonic `control_generation`;
- desired `enabled` state;
- desired `interval_minutes`;
- optional exact `next_wake_at`;
- `updated_at` evidence.

The extension validates the record against both the live runtime catalog and the locally configured conversation binding. Binding or revision mismatches fail closed.

The applied acknowledgement is scoped to `(bindingRevision, controlGeneration, localGeneration)`. Re-reading the same desired generation is idempotent; local pacing drift is repaired; a consumed one-shot `NEXT` is not replayed indefinitely.

## Discovery and lifecycle

Chat Bridge 0.6.0 owns a dedicated one-minute `chrome.alarms` poll for GitHub control state. Every MV3 worker activation ensures that alarm exists, including manual unpacked-extension Reload. Chrome alarms survive service-worker suspension, so a remotely paused chat can later discover `RESUME` even when it has no conversation wake alarm.

No GitHub token is shipped in the extension. It only reads the existing public remote runtime endpoint.

The global Bridge Master switch remains local operator state and is never changed by a conversation desired-state record.

## Legacy LAB behavior

For a GitHub-managed chat, legacy assistant schedule controls (`STOP`, `PAUSE`, `RESUME`, `NEXT`, `INTERVAL`) and user `OP:ENABLE` / `OP:DISABLE` / `OP:INTERVAL` are compatibility no-ops. They are recognized only so old content can dedupe/terminate cleanly; GitHub remains authoritative.

Binding controls (`ADD`, `REBIND`, `REMOVE`) and Bridge maintenance/diagnostic paths remain explicit migration surfaces for now. They are not the normal pacing/status transport.

## Live field proof

The canonical daily-Chrome conversation `chat-e8ad8275` was migrated and validated end-to-end on 2026-09-30:

1. GitHub desired state generation 1: `PAUSED` (`enabled=false`).
2. Generation 2: `RESUME`.
3. Generation 3: exact `NEXT` for two minutes later.
4. Chat Bridge 0.6.0 discovered the GitHub state, inserted the wake prompt into the correct ChatGPT composer and successfully submitted it.
5. The resulting wake arrived in the same bound conversation with the immutable `host-ops` envelope.
6. Generation 4 returned the chat to `PAUSED` with `next_wake_at=null`.

This live proof demonstrates the complete normal path:

```text
GitHub chat-bridge-state
  -> Chat Bridge 0.6.0 remote reconcile
  -> chrome.alarms
  -> exact ChatGPT conversation
  -> composer
  -> Send
  -> planner wake
```

No assistant `[LAB:*]` schedule marker was required.

## Verification

The exact 0.6.0 candidate before release metadata passed all five CI gates:

- full test/lint/compile job;
- coverage;
- Python 3.14;
- real-extension browser smoke;
- macOS ARM64 smoke (291 tests, `OK`).

Release metadata and canonical documentation are reverified on the final 4.19.9 SHA before advancing `main`.

## Versions

```text
Local Agent:      4.19.9
Chat Bridge:      0.6.0
content protocol: 13
assistant guard:  8
runtime schema:    3 + optional conversation_controls
```

## Rollback

The immediate source rollback point is `v4.19.8`. The live `chat-bridge-state` desired record should be left `PAUSED` before rolling back the extension so a stale scheduler cannot emit a surprise wake.
