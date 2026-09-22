# Assistant delivery-timeout re-audit

Status: pre-main review of `work/chat-delivery-timeout-detection`. Production `main` and the installed Local Agent runtime remain unchanged.

## What changed

The runtime behavior change is in **Local Agent Chat Bridge**, not in the Local Agent daemon/executor/scheduler.

Changed runtime surfaces are limited to `chat_bridge/` browser-extension code:

- DOM recognition of the captured ChatGPT assistant timeout;
- assistant-error observation and Retry coordination;
- worker-side retry authorization/accounting;
- unresolved-timeout wake gating;
- stale-guard refresh and lifecycle cleanup;
- Chat Bridge manifest version `0.5.10`.

Repository verification gained additional Bridge browser smoke coverage. Documentation records the new DOM/recovery contract. No `local_agent/` Python runtime implementation file is changed by this candidate, and `local_agent.version.RELEASE_VERSION` is still `4.18.23` while this remains a candidate.

## Re-audited architecture

The ownership split remains coherent:

1. `dom_contract.js` is recognition-only and requires the timeout to be the latest rendered conversation turn.
2. `exhaustion_guard.js` owns DOM observation and the native Retry click. It never creates a replacement user message.
3. `worker_transport.js` owns exact tab/conversation preflight, guard readiness and unresolved-timeout wake gating support.
4. `worker_assistant_errors.js` owns policy: Bridge ownership, preferred-tab restriction, binding/generation revalidation, persistent bounded attempt accounting and terminal fail-closed state.
5. `worker_delivery.js` blocks fresh scheduled/manual wakes while current DOM still contains the timeout.
6. `worker_conversations.js` clears retired recovery state on rebind/remove/re-add.
7. `worker_events.js` remains routing-only and `service_worker.js` remains composition-only.

No timeout-recovery policy leaks into Local Agent repository workers, executor, resource admission, process lifecycle or supervisor scheduling.

## Safety/race review

Automatic Retry requires the exact configured conversation and preferred tab, an unchanged binding revision and generation, enabled Master/chat state, a Bridge-owned triggering prompt, the same live timeout snapshot, no active assistant generation and a still-usable Retry button.

The durable budget is consumed at worker authorization before the browser click. This is intentionally fail-closed: a narrow DOM race may spend an attempt without producing a click, but it cannot produce an extra click or a duplicate user prompt. Under-retry is preferred to replay ambiguity.

The captured error after a normal operator-authored message is detected as `assistant_delivery_timeout_unowned` but is **not** auto-clicked. This preserves the boundary between autonomous Bridge wakes and arbitrary operator prompts. It still blocks a new Bridge wake while the failed turn remains current, preventing a second user turn from being layered on top of the unresolved error.

## Additional verification added during re-audit

The re-audit added two negative-path checks beyond the earlier candidate suite:

- `assistant_error_cancellation.test.js` proves Master-off and disabled-chat authorization cannot consume retry budget;
- `bridge_assistant_error_unowned_smoke.cjs` loads the real unpacked extension in isolated offline Chromium, renders a timeout after a manual operator message, proves Retry is never auto-clicked, proves `Run now` is blocked as `assistant_recovery_pending`, removes the stale timeout card, and proves normal Bridge wake delivery resumes afterward.

These tests are part of the standard Bridge validation/browser profile before any main advance.

## Main/self-update boundary

Local Agent production self-update watches `origin/main` every 60 seconds when its own checkout is clean and on `main`. A new fast-forward main commit is installed, validated and followed by `restart_self("self_update")`.

Therefore **merging this candidate to `main` is already the restart boundary**. There is not a safe assumption that main can be advanced now and the Local Agent restart can be postponed manually.

While Local Agent is being used for other code work, leave PR #84 unmerged. The safe stopping point is a green, mergeable, reviewed candidate PR with production `main` unchanged.

## Remaining live-only checks

Sandbox/CI cannot prove current production ChatGPT server/UI behavior. The remaining live smoke is limited to confirming the production page still exposes the expected timeout structure/Retry control and behaves consistently during native Retry. Any mismatch is fail-closed.
