# Chat Bridge event-driven wake TODO

Branch: `feature/chat-bridge-event-wake`

This checklist is intentionally implementation-ordered. Do not skip the audit and protocol phases: the feature crosses Local Agent result publication, Chrome MV3 lifecycle, durable extension state and hard-bound conversation routing.

## Phase 0 — preimplementation audit and freeze the contract

- [ ] Inventory every Local Agent path that produces a terminal `.agent/results/<task-id>.json` result.
- [ ] Inventory deferred/pending publication recovery paths and identify the exact point where remote result availability is proven.
- [ ] Confirm terminal status values currently emitted for success, failure, rejection and cancellation.
- [ ] Confirm whether `task_digest` is present on every terminal result; document fallback if not.
- [ ] Identify the existing Local Agent state-directory owner to host the event outbox without adding cwd-relative state.
- [ ] Identify current daemon/runtime cleanup policy so outbox retention does not conflict with metadata cleanup.
- [ ] Map current Chat Bridge schema fields/migrations and select the minimum new persisted state for watches/events.
- [ ] Map worker delivery entry points so event wake reuses the existing content activation/submission path.
- [ ] Audit all STOP/PAUSE/RESUME/remove/rebind flows and specify exact task-watch behavior for each.
- [ ] Audit extension startup/reload/service-worker event handlers and select one native connection owner.
- [ ] Decide native host package/module name and executable entry point.
- [ ] Decide macOS Native Messaging host manifest installation/removal path through existing platform helpers.
- [ ] Decide development extension-id strategy: generated allowlist from installed id vs pinned identity.
- [ ] Record exact event payload field limits and recent-cache/outbox bounds.
- [ ] Record a native protocol version and handshake contract before implementation.
- [ ] Add negative security cases to the test plan before writing transport code.

Exit criterion: architecture document contains no unresolved routing or durability ambiguity that would force a task-contract redesign during implementation.

## Phase 1 — Local Agent durable event outbox

- [ ] Add a dedicated event schema/outbox owner module.
- [ ] Define `task_result_ready` schema v1 with bounded metadata only.
- [ ] Generate stable/deduplicable event identity.
- [ ] Atomically append events to durable local state.
- [ ] Add ACK state and safe compaction/pruning.
- [ ] Bound event count, age and total serialized size.
- [ ] Make corrupt event/outbox entries explicit diagnostics rather than silent skips.
- [ ] Emit an event only after successful remote terminal-result publication.
- [ ] Cover deferred publication recovery so a result that becomes remotely available later emits exactly one logical event.
- [ ] Ensure event-side failure never changes an already-authoritative task result from success/failure to another task status.
- [ ] Add outbox health to Local Agent diagnostics.
- [ ] Add unit tests for append, duplicate, ACK, replay, corruption, bounds and restart recovery.

Exit criterion: Local Agent can produce/replay/ack exact terminal-result notifications without Chrome installed and without changing executor behavior.

## Phase 2 — Native Messaging host

- [ ] Add a minimal native host executable/module.
- [ ] Implement Chrome Native Messaging length-prefixed JSON framing.
- [ ] Add strict handshake with protocol version and bounded capability fields.
- [ ] Stream/replay unacknowledged outbox events.
- [ ] Accept only protocol ACK/health requests; no generic command dispatch.
- [ ] Reject malformed, oversized, unknown-version and unknown-action messages.
- [ ] Add deterministic stderr diagnostics that do not contain task output/secrets.
- [ ] Add macOS host-manifest renderer/installer/remover.
- [ ] Restrict `allowed_origins` to the expected extension id.
- [ ] Add installation diagnostics for missing executable, wrong manifest and wrong extension id.
- [ ] Add standalone protocol tests using stdin/stdout pipes.
- [ ] Add reconnect/replay integration tests.

Exit criterion: a fake extension client can receive and ACK durable Local Agent events across native-host restart without any executor authority exposed.

## Phase 3 — Bridge native connection and durable ingestion

- [ ] Add `nativeMessaging` permission to the extension candidate manifest.
- [ ] Add one service-worker-owned `connectNative()` lifecycle.
- [ ] Implement bounded reconnect backoff after `Port.onDisconnect`.
- [ ] Validate native handshake/protocol before accepting events.
- [ ] Validate every event before state mutation.
- [ ] Persist accepted events before sending host ACK.
- [ ] Add bounded persisted recent-event cache with TTL/oldest-first eviction.
- [ ] Deduplicate replayed `event_id` values.
- [ ] Preserve cached events across MV3 service-worker restart.
- [ ] Expose native transport health through `LAB:CAPABILITIES`/`LAB:DEBUG`.
- [ ] Keep ordinary scheduled Bridge operation functional when the native host is absent/incompatible.
- [ ] Add unit tests for receive -> persist -> ACK ordering and crash/restart boundaries.

Exit criterion: Bridge durably receives native events without yet waking any conversation.

## Phase 4 — exact task-watch routing

- [ ] Add strict `[LAB:WAIT_TASK=<task-id>]` parsing to `control_protocol.js`.
- [ ] Define task-id length/character bounds compatible with Local Agent task ids.
- [ ] Persist one active task watch per conversation.
- [ ] Scope every watch to stored repository id + stored `agent_binding`.
- [ ] Reject a second conversation attempting to own the same repository/binding/task tuple.
- [ ] On watch registration, check recent cached events immediately to close the short-task race.
- [ ] Define STOP behavior: clear watch.
- [ ] Define remove behavior: clear watch and pending event wake.
- [ ] Define rebind behavior: clear old watch/event state before new bootstrap.
- [ ] Define PAUSE behavior: retain watch/event but block normal delivery until resumed.
- [ ] Define RESUME behavior: reconcile retained pending event before ordinary scheduled wake.
- [ ] Define stale-watch cleanup during a normal planner reconciliation.
- [ ] Add current-watch information to diagnostics.
- [ ] Add same-repository/two-chat negative routing tests.

Exit criterion: an event can be matched to one and only one conversation without adding chat identity to Local Agent task JSON.

## Phase 5 — event wake delivery

- [ ] Add pending event-wake state owned by the service worker.
- [ ] Build a fixed event wake prompt containing only bridge-owned envelope + event type + exact task id.
- [ ] Reuse existing content activation, exact-URL authorization and submission confirmation.
- [ ] Reuse existing draft-preservation behavior.
- [ ] Handle assistant-generating/send-button-not-ready without dropping the event.
- [ ] Keep pending event when the exact ChatGPT tab is absent.
- [ ] Do not auto-open arbitrary ChatGPT tabs in v1.
- [ ] Clear the active task watch only after the pending event wake is durably owned/consumed according to the chosen state transition.
- [ ] Ensure duplicate event delivery cannot submit duplicate logical wake messages.
- [ ] Preserve normal fallback alarm reconciliation.
- [ ] Add event-delivery status to diagnostics.
- [ ] Add browser tests for busy generation, draft present, missing tab, duplicate event and worker restart.

Exit criterion: one terminal result event wakes exactly the owning configured conversation through the existing safe delivery path.

## Phase 6 — planner pacing integration

- [ ] Update autonomous planner documentation to prefer `WAIT_TASK` after queueing when native event capability is healthy.
- [ ] Remove the normal need for an early 2-minute healthy-task poll in the event-capable path.
- [ ] Keep current `NEXT` behavior as explicit degraded-mode fallback.
- [ ] Keep the normal/default alarm as bounded reconciliation even while waiting on an event.
- [ ] Define capability feedback that lets the planner distinguish healthy event transport from fallback mode.
- [ ] Ensure a native disconnect does not leave a conversation with no future reconciliation alarm.
- [ ] Update Chat Bridge README/control catalog.
- [ ] Perform downstream planner-documentation audit required by `AGENTS.md` if the planner contract changes.

Exit criterion: healthy Local Agent tasks normally create zero no-change polling turns between queue and terminal result availability.

## Phase 7 — end-to-end validation

- [ ] Run focused Python/event-outbox/native-host tests.
- [ ] Run focused Chat Bridge protocol/state tests.
- [ ] Run full `python scripts/verify.py --only bridge` or its current canonical equivalent.
- [ ] Run disposable Chromium browser profile tests.
- [ ] Install the candidate native host on the real Mac.
- [ ] Verify a short read-only task that finishes before `WAIT_TASK` registration.
- [ ] Verify a multi-minute task produces no repeated healthy polling turns.
- [ ] Verify success result wake.
- [ ] Verify failed task wake.
- [ ] Verify rejected/binding-failure task wake where a terminal result exists.
- [ ] Verify cancelled task wake.
- [ ] Verify deferred result publication does not wake early and wakes after publication succeeds.
- [ ] Verify two conversations on the same repository: only watch owner wakes.
- [ ] Verify another repository never wakes from the event.
- [ ] Kill native host during a task and verify replay/fallback.
- [ ] Restart extension service worker between native receive and ChatGPT delivery.
- [ ] Restart Chrome with a pending/outbox event.
- [ ] Restart Local Agent before and after result publication.
- [ ] Verify ordinary polling-only behavior with the native host completely absent.
- [ ] Verify event flood/storage bounds and no unbounded state growth.

Exit criterion: real E2E evidence demonstrates lower latency/no polling spam without weakening hard binding or fallback recovery.

## Phase 8 — release preparation

- [ ] Review threat model and permission change (`nativeMessaging`).
- [ ] Update `docs/SECURITY_MODEL.md`.
- [ ] Update `docs/AUTONOMOUS_CHAT_LOOP.md`.
- [ ] Update `chat_bridge/README.md`.
- [ ] Update `docs/ARCHITECTURE.md` if module ownership changes.
- [ ] Update installer/operations documentation.
- [ ] Complete downstream documentation synchronization required by `AGENTS.md`.
- [ ] Bump release/version metadata only when implementation is release-ready.
- [ ] Record focused, full CI, Chromium and real-macOS evidence for the exact candidate SHA.
- [ ] Merge only after explicit release decision.

## Explicitly deferred ideas

Do not mix these into event-wake v1 unless testing proves they are required:

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
