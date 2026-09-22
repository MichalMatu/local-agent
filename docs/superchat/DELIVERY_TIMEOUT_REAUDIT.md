# Assistant delivery-timeout re-audit

Status: released as Local Agent 4.18.24 / Chat Bridge 0.5.10 after exact-head CI validation and an explicit operator-approved restart window.

The runtime behavior change is in **Local Agent Chat Bridge**, not in the Local Agent daemon/executor/scheduler. The exact released SHA is `474000b5d4b015958fe92be491968dc4625b4a84`.

## Architecture summary

- `dom_contract.js` recognizes only the current captured timeout shape.
- `exhaustion_guard.js` observes the DOM and clicks ChatGPT's native Retry control; it never creates a replacement user message.
- `worker_transport.js` owns exact tab/conversation preflight and unresolved-timeout wake gating.
- `worker_assistant_errors.js` owns Bridge ownership checks, preferred-tab restriction, binding/generation revalidation, durable bounded attempts and fail-closed exhaustion.
- `worker_delivery.js` blocks fresh wakes while the timeout remains unresolved.
- lifecycle cleanup prevents stale retry state crossing rebind/remove/re-add boundaries.

Automatic Retry requires the exact configured conversation and preferred tab, unchanged binding revision and generation, enabled Master/chat state, a Bridge-owned triggering prompt, the same live timeout snapshot, no active assistant generation and a usable Retry button. Operator-authored timeouts are diagnostic-only and never auto-clicked.

The retry budget is consumed before the click and is intentionally fail-closed: a race may spend an attempt without a click, but it cannot cause a duplicate user prompt. Retry authorization is revalidated after durable reservation to close the TOCTOU window.

## Verification

Exact-head GitHub Actions run `35728654550` passed test, coverage, Python 3.14, macOS smoke and real unpacked-extension Chromium browser smoke. The browser matrix covers one-retry recovery, stale-card rejection, >8 s same-node generation, exactly three failed retries, operator-authored timeout non-recovery and full page-reload continuation without duplicate submission.

## Production update

Production `main` was fast-forwarded to the exact validated SHA. The installed Local Agent then self-updated and restarted through its normal validated path. Remote daemon status confirmed Local Agent `4.18.24`, idle, on `self_revision = 474000b5d4b015958fe92be491968dc4625b4a84`. A subsequent explicit `self_update` control completed with `result: no_update`, confirming the restarted daemon was already current.

The remaining live-only check is reloading the installed Chat Bridge from the updated checkout and observing the real ChatGPT timeout/Retry DOM when the condition occurs.
