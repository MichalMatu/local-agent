# Chat Bridge event-driven wake TODO

Branch: `feature/chat-bridge-event-wake`

Status: implementation candidate. Keep PR #77 draft and **do not merge to `main`** until an explicit release decision is made. A `main` update may trigger Local Agent autoupdate.

Final live-loaded code candidate before evidence-only docs:

- extension: `0.5.12`
- commit: `8da2dd576fd2d5e076961886492f59c0164fdbf2`
- CI: run #801 (`35117866465`), all five jobs green

## Phase 0 — contract and authority

- [x] Inventory terminal result publication paths and deferred publication recovery.
- [x] Emit `task_result_ready` only after successful authoritative result publication.
- [x] Keep event persistence separate from Chat Bridge runtime state.
- [x] Reuse exact-tab/content delivery rather than add a second execution path.
- [x] Define STOP/PAUSE/RESUME/remove/rebind/Master semantics.
- [x] Keep Native Messaging notification-only: no shell, terminal, arbitrary file/log access, task create/cancel or repository rebind.
- [x] Freeze event schema v1 and native protocol v1.
- [x] Preserve exact hard binding: repository id + repository name + `agent_binding` + task id.

## Phase 1 — durable Local Agent outbox

- [x] Dedicated `result_events` module.
- [x] Bounded `task_result_ready` metadata schema.
- [x] Deterministic event identity.
- [x] Atomic durable writes and fsync.
- [x] ACK deletion and bounded count/age/size pruning.
- [x] Full payload/identity validation before replay.
- [x] Corrupt/tampered entry pruning.
- [x] Re-publication idempotence.
- [x] Event-side failure cannot rewrite authoritative task outcome.
- [ ] Surface `outbox_health()` in a user-facing diagnostic only if operational experience shows it is needed; this is observability, not correctness.

## Phase 2 — Native Messaging host

- [x] Minimal read-only host with bounded Chrome framing.
- [x] Versioned handshake and session-scoped ACK.
- [x] Continuous durable outbox replay while connected.
- [x] Exact extension-origin validation and registration.
- [x] macOS manifest/wrapper installer and uninstall.
- [x] Installer diagnostics for wrong origin/path/mode/executable.
- [x] Real operator-Mac transport works with protocol v1.
- [x] Final installer status on the operator Mac reported `healthy = true`, `problems = []`, manifest `0o600`, wrapper `0o700`, executable, matching expected wrapper and exact registered extension origin.

## Phase 3 — Bridge ingestion and connection lifecycle

- [x] `nativeMessaging` permission.
- [x] On-demand service-worker-owned native lifecycle.
- [x] Bounded reconnect backoff starting at 5 seconds.
- [x] Handshake/protocol validation before acceptance.
- [x] Persist event state before ACK.
- [x] Bounded recent-event cache with replay deduplication.
- [x] State survives MV3 worker restart.
- [x] `LAB:CAPABILITIES`, `STATUS` and `DEBUG` expose bounded event health.
- [x] Native transport absence leaves alarm fallback intact.
- [x] PAUSE/operator-disable/Master-off suspend native transport without silently discarding retained ownership.

## Phase 4 — exact task watch routing

- [x] Strict `[LAB:WAIT_TASK=<task-id>]` parser and task-id bounds.
- [x] One active exact watch per conversation.
- [x] Every Local Agent task JSON remains bound to the exact `agent_binding` when execution is enabled; `bridge/operator-only` conversations do not create Local Agent project task files.
- [x] Never infer, substitute, inspect, queue, cancel, or execute work for another repository.
- [x] Exact repository/binding/task matching.
- [x] Duplicate ownership rejection with fallback retained.
- [x] Event-before-watch fast-task race recovery.
- [x] STOP/remove/rebind clear ownership; PAUSE retains it.
- [x] Binding epoch (`bindingRevision` + `bindingSetAt`) prevents stale ownership crossing a rebind.

## Phase 5 — event wake delivery and recovery

- [x] Durable pending wake state.
- [x] Fixed event wake envelope contains exact event/task and hard-binding policy.
- [x] Existing exact-tab activation/authorization reused.
- [x] Missing tab/transient send failure does not consume pending event.
- [x] `assistant_busy`, `send_button_not_ready`, content readiness failures and other retryable states retain the pending event.
- [x] Pending event is consumed only after delivery returns `ok`.
- [x] Scheduled fallback remains active.
- [x] Live watch-before-event wake reached ChatGPT.
- [x] Live event-before-watch durable replay reached ChatGPT.
- [x] Exact native-host kill -> durable outbox -> reconnect -> replay -> live ChatGPT delivery passed (`evt-4174b0dd4c6e6142746e5d32146474ed`).
- [x] Full Chrome restart on 0.5.12 replayed and accepted the exact outbox event after startup: `evt-5a518b7b5f2d3a5d5f5506a33d39ea33`, accepted at `2026-09-16T15:56:27.716Z`.
- [x] Full Chrome restart retained that exact event as `pendingWake` when the renderer returned `assistant_busy`, with one-minute retry scheduled instead of losing/consuming it.
- [ ] Observe a successful immediate ChatGPT send after full Chrome restart while the renderer is not busy. The final operator run proved replay/retention but did not observe this final UI delivery step.

0.5.12 cold-start mitigation is bounded rather than permanent polling: startup arms three one-shot reconciliation passes at approximately 1 s, 3 s and 8 s to refresh configured restored tabs and re-arm pending wakes. `tabs.onUpdated(status=complete)` remains an additional signal.

## Phase 6 — planner pacing and token budget

- [x] Runtime prompts prefer `WAIT_TASK` for exact Local Agent tasks.
- [x] `WAIT_TASK` combines event-driven wake with alarm fallback.
- [x] `NEXT` remains for genuinely time/external checks.
- [x] No healthy-task 30-second polling requirement.
- [x] Native disconnect cannot remove scheduled reconciliation.
- [x] Documentation describes the hybrid model.
- [x] Repeated prompts were reduced without weakening explicit hard-binding/Master safety invariants.
- [x] Measured candidate prompt maxima: bootstrap 1556 chars, normal wake 1041 chars, event wake 661 chars.

## Phase 7 — validation

Automated/live evidence completed:

- [x] Focused outbox/native-host/installer tests.
- [x] Bridge protocol/state/routing tests.
- [x] Fast-task and duplicate-owner races.
- [x] Cross-repository/binding isolation.
- [x] Pause/resume/Master/operator lifecycle tests.
- [x] Pending-event transient-failure retention.
- [x] MV3 restart persistence.
- [x] Native host duplex replay/ACK integration.
- [x] Tamper/identity pruning tests.
- [x] Browser startup regression that covers restored tabs appearing only after `onStartup`.
- [x] Exact final code candidate `8da2dd576fd2d5e076961886492f59c0164fdbf2` passed CI #801 (`35117866465`) with `test`, `bridge-browser`, `coverage`, `python-314` and `macos-smoke` all green.
- [x] Real Chrome loaded 0.5.12 with content protocol `7/7` and exact binding retained.
- [x] Installer health passed on the operator Mac.
- [x] Native host kill/restart durable replay passed end-to-end.
- [x] Chrome full-restart outbox replay/event acceptance/pending retention passed on 0.5.12.

Evidence-only documentation commits move the PR head. Final CI for the documentation-synchronized PR head is recorded in the PR conversation/final review rather than by making another self-invalidating documentation edit.

Still open as **release evidence**, not implementation blockers for freezing this draft branch:

- [ ] Real short Local Agent task whose authoritative `.agent/results/<task-id>.json` publication precedes the wake.
- [ ] Real multi-minute task with no repeated healthy polling turns.
- [ ] Real done/failed/rejected/cancelled result wakes.
- [ ] Real deferred result publication wake only after successful publication.
- [ ] Local Agent restart around result publication.
- [ ] Polling-only fallback with Native Messaging intentionally absent.
- [ ] Successful immediate ChatGPT injection after full Chrome restart when renderer is not busy.

These semantic task gates cannot be manufactured in this hard-bound `local-agent` conversation because it is intentionally `bridge/operator-only` / execution-disabled.

## Phase 8 — release preparation

- [x] Threat model and `nativeMessaging` permission reviewed.
- [x] `docs/SECURITY_MODEL.md` updated.
- [x] `docs/AUTONOMOUS_CHAT_LOOP.md` updated.
- [x] `chat_bridge/README.md` updated.
- [x] Native host installer/health documentation added.
- [x] Prompt/token budget and hybrid wake semantics recorded.
- [x] Final 0.5.12 Chrome-restart evidence recorded in `LIVE_EVIDENCE_2026-09-16.md`.
- [ ] Update top-level architecture ownership map only if required by a later release review.
- [ ] Mark PR ready only after explicit release decision.
- [ ] **Merge only after explicit user decision. Merging to `main` may trigger autoupdate and is intentionally forbidden during this pre-merge audit.**

## Explicitly deferred

Do not mix these into event-wake v1 without a new design/security review:

- arbitrary terminal access from Chat Bridge;
- raw daemon log streaming into ChatGPT;
- arbitrary filesystem reads through Native Messaging;
- task cancellation or creation through the native host;
- automatic ChatGPT tab/conversation creation;
- repository rebind through native events;
- continuous command-output streaming.
