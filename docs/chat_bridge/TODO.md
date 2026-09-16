# Chat Bridge event-driven wake TODO

Branch: `feature/chat-bridge-event-wake`

Status: implementation candidate. Keep PR #77 draft and **do not merge to `main`** until the real-Mac gates below are completed and an explicit release decision is made.

## Phase 0 — preimplementation audit and contract

- [x] Inventory terminal result publication paths and deferred publication recovery.
- [x] Place event emission after successful authoritative result push.
- [x] Confirm result status/digest handling and bounded fallback for missing digest.
- [x] Use the existing Local Agent application-support state directory for the outbox.
- [x] Keep event persistence separate from Chat Bridge schema v3.
- [x] Reuse the existing exact-tab/content delivery path.
- [x] Define STOP/PAUSE/RESUME/remove/rebind/Master semantics.
- [x] Define one service-worker-owned Native Messaging lifecycle.
- [x] Freeze event schema v1, native protocol v1, payload limits and identity fields.
- [x] Define exact extension-id registration instead of wildcard/pinned guessed identity.
- [x] Record negative security cases before release.

## Phase 1 — Local Agent durable event outbox

- [x] Dedicated `result_events` module.
- [x] Bounded `task_result_ready` metadata schema.
- [x] Stable deterministic event identity.
- [x] Atomic durable outbox writes and fsync.
- [x] ACK deletion and bounded pruning.
- [x] Count, age and serialized-size limits.
- [x] Full payload/identity validation before replay.
- [x] Corrupt/tampered event pruning.
- [x] Event only after successful result push.
- [x] Re-publication idempotence.
- [x] Event-side failure cannot rewrite authoritative task outcome.
- [x] Unit coverage for append, duplicate, ACK, TTL, tamper and identity mismatch.
- [ ] Surface Local Agent outbox health in a user-facing Local Agent diagnostic/status surface if operational experience shows it is needed. `outbox_health()` already exists; this is observability, not correctness.

## Phase 2 — Native Messaging host

- [x] Minimal read-only native host module.
- [x] Chrome length-prefixed JSON framing and bounds.
- [x] Versioned handshake.
- [x] Continuous outbox replay while connected, including events created after handshake.
- [x] ACK-only extension-to-host event control path; no generic command dispatch.
- [x] Exact Chrome extension caller-origin validation.
- [x] macOS manifest/wrapper installer and uninstall.
- [x] Exact `allowed_origins` registration.
- [x] Installer health diagnostics for wrong origin/path/mode/executable.
- [x] Protocol/framing/origin tests.
- [x] Duplex integration test: handshake -> later event -> delivery -> ACK -> outbox removal.
- [x] Native host was installed and healthy on the operator Mac for the previous 0.5.10 live candidate; final exact 0.5.11 loaded-head health still needs confirmation.

## Phase 3 — Bridge native connection and durable ingestion

- [x] `nativeMessaging` extension permission.
- [x] On-demand service-worker-owned native lifecycle.
- [x] Bounded reconnect backoff.
- [x] Handshake/protocol validation before event acceptance.
- [x] Event validation before state mutation.
- [x] Persist event state before ACK.
- [x] Bounded recent-event cache with TTL/eviction.
- [x] Replay deduplication.
- [x] State survives MV3 worker restart.
- [x] `LAB:CAPABILITIES`, `STATUS` and `DEBUG` expose bounded event health.
- [x] Native transport absence leaves ordinary alarm operation functional.
- [x] Native process is suspended while PAUSE/operator-disable/Master-off prevents delivery.
- [x] Resume/re-enable/Master-on reconnects retained watches.

## Phase 4 — exact task-watch routing

- [x] Strict `[LAB:WAIT_TASK=<task-id>]` parser and task-id bounds.
- [x] One active exact watch per conversation.
- [x] Scope watch to repository id + repository name + `agent_binding` + task id.
- [x] Reject duplicate ownership of the same exact tuple; second chat retains alarm fallback.
- [x] Immediate recent-cache lookup closes fast-task race.
- [x] STOP clears watch/pending wake.
- [x] Remove clears watch/pending wake.
- [x] Rebind clears old watch/pending wake.
- [x] PAUSE retains watch but blocks event delivery/native connection.
- [x] RESUME reconciles retained pending event/watch.
- [x] Current watch appears in bounded diagnostics.
- [x] Cross-binding/repository and same-task ownership negative tests.
- [x] No arbitrary stale-watch TTL: fallback wakes let the planner inspect exact task state; long legitimate tasks are not silently abandoned by a guessed timeout.

## Phase 5 — event wake delivery

- [x] Durable pending event wake state.
- [x] Fixed event envelope contains event type + exact task id and hard binding policy.
- [x] Existing exact-tab/content activation and authorization reused.
- [x] Existing draft-preservation behavior reused.
- [x] Missing tab does not consume pending event.
- [x] `send_button_not_ready`/transient delivery does not consume pending event.
- [x] Pending event is consumed only after delivery returns `ok`.
- [x] No arbitrary ChatGPT tab auto-open.
- [x] Duplicate native replay cannot create a second exact task watch delivery owner.
- [x] Scheduled reconciliation remains active.
- [x] Event-delivery state appears in diagnostics.
- [x] MV3 restart before native receive and between receive/delivery is covered.
- [x] Live 0.5.10 synthetic watch-before-event wake reached ChatGPT and cleared exact pending/watch after confirmed delivery.
- [x] Live 0.5.10 synthetic event-before-watch durable outbox replay reached ChatGPT and cleared exact pending/watch after confirmed delivery.
- [ ] Real live ChatGPT DOM smoke on the final exact 0.5.11 branch head.

## Phase 6 — planner pacing and token-budget integration

- [x] Runtime bootstrap/wake prompts prefer `WAIT_TASK` after queueing.
- [x] Hybrid model is explicit: `WAIT_TASK` uses action-driven wake plus alarm fallback; manual `NEXT` remains for genuinely time/external rechecks.
- [x] Remove normal early polling requirement for healthy watched tasks.
- [x] Keep `NEXT` for genuinely time-based checks.
- [x] Keep default alarm as bounded fallback while waiting.
- [x] Capability/debug feedback exposes native/event state.
- [x] Native disconnect cannot remove scheduled reconciliation.
- [x] `docs/AUTONOMOUS_CHAT_LOOP.md` describes the hybrid model and CI contract enforces the planner pacing rules.
- [x] `chat_bridge/README.md` updated.
- [x] Repeated prompt payload was reduced without weakening explicit hard-binding/Master safety invariants.
- [x] Measured 0.5.11 worst-case prompt sizes: bootstrap 1556 chars, normal wake 1041 chars, event wake 661 chars.

## Phase 7 — validation

Automated candidate evidence:

- [x] Focused Python outbox/native-host/installer tests.
- [x] Focused Chat Bridge protocol/state/routing tests.
- [x] Fast-task race test.
- [x] Same exact task / two-chat conflict test.
- [x] Cross-repository/binding isolation test.
- [x] Pause/resume/Master/operator native-lifecycle tests.
- [x] Pending-event transient-failure retention test.
- [x] MV3 restart persistence test.
- [x] Native host event-created-after-handshake duplex test.
- [x] Tampered outbox identity/pruning tests.
- [x] Installer wrong-ID/path/executable diagnostics tests.
- [x] Pre-documentation 0.5.11 code candidate `adfc62d8754ae57e96eb7892041de6b566a3d20a` passed CI #789 (`35110618291`) with `test`, `bridge-browser`, `coverage`, `python-314` and `macos-smoke` all green.
- [x] #789 disposable Chromium `bridge-browser` smoke passed on that same exact code candidate.

Still required before release/merge:

- [ ] Final full CI green for the documentation-synchronized exact branch SHA; this documentation commit intentionally moves the head after #789.
- [ ] Load/reload the final exact 0.5.11 branch SHA in the real Chrome profile.
- [ ] Confirm native-host `status --extension-id <id>` remains healthy with that loaded candidate path.
- [ ] Real short Local Agent task that finishes before `WAIT_TASK` registration wakes correctly; synthetic event injection is not sufficient for this semantic gate.
- [ ] Real multi-minute task completes with no repeated healthy polling turns.
- [ ] Real success result wake.
- [ ] Real failed result wake.
- [ ] Real rejected/binding-failure result wake.
- [ ] Real cancelled result wake.
- [ ] Real deferred result publication wakes only after successful publication.
- [ ] Kill/restart native host and verify replay/fallback.
- [ ] Restart Chrome with a pending/outbox event and verify recovery.
- [ ] Restart Local Agent around result publication and verify no lost authoritative result/event.
- [ ] Verify polling-only fallback with native host intentionally absent.

## Phase 8 — release preparation

- [x] Threat model and `nativeMessaging` permission reviewed.
- [x] `docs/SECURITY_MODEL.md` updated.
- [x] `docs/AUTONOMOUS_CHAT_LOOP.md` updated.
- [x] `chat_bridge/README.md` updated.
- [x] Development architecture/TODO documentation updated.
- [x] Native host installer/health documentation added.
- [x] Prompt/token budget and hybrid wake semantics recorded in the pre-merge audit/TODO.
- [ ] Update `docs/ARCHITECTURE.md` if final release review requires the event modules in the top-level ownership map.
- [ ] Complete any remaining release-document synchronization required by `AGENTS.md` after final real-Mac evidence.
- [ ] Bump release/version metadata only when explicitly preparing release.
- [ ] Record final exact-SHA CI + real-macOS evidence without changing behavior afterward.
- [ ] Mark PR ready only after explicit release decision.
- [ ] **Merge only after explicit user decision. Merging to `main` may trigger autoupdate and is intentionally forbidden during this pre-merge audit.**

## Explicitly deferred

Do not mix these into event-wake v1 without a new design/security review:

- arbitrary terminal access from Chat Bridge;
- raw daemon log streaming into ChatGPT;
- arbitrary filesystem reads through Native Messaging;
- task cancellation through the native host;
- task creation through the native host;
- automatic ChatGPT tab/conversation creation;
- removal of scheduled reconciliation;
- repository rebind through native events;
- continuous command-output streaming.

If later diagnostics need more local visibility, design a separate bounded read-only protocol around exact task ids and explicit data classes rather than adding a generic shell/log endpoint.
