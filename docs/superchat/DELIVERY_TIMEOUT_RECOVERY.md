# ChatGPT delivery-timeout recovery

Status: implemented as a release candidate on `work/chat-delivery-timeout-detection`. Production `main`, the installed Local Agent daemon and the operator's installed Chat Bridge are not changed by this branch work.

## Captured evidence

A saved ChatGPT page from 2026-09-22 contains a terminal assistant-side failure after a normal user message. The relevant rendered structure is:

```html
<div data-message-author-role="assistant" data-message-id="...">
  <div class="... text-token-text-error ...">
    <p>Message delivery timed out. Please try again.</p>
    <button data-testid="regenerate-thread-error-button">Retry</button>
  </div>
</div>
```

Stable signals used by the detector are the assistant message boundary, `.text-token-text-error`, the captured timeout text, the explicit `regenerate-thread-error-button`, fallback exact `Retry` button text and the current assistant-turn identity.

The capture proves that this failure occurs after the user message has already been accepted. It is therefore not the existing `delivery_unconfirmed` transport case.

## Why the previous Bridge missed it

Normal delivery is considered `sent` once the exact submitted user message appears in the DOM. That is intentionally transport confirmation only. A later ChatGPT response-generation/delivery failure occurs after `worker_delivery.js` has finished the original submission.

The previous assistant-control scanner could see the timeout message, but because it contained no LAB command it had no typed recovery path.

## Implemented recovery path

The branch keeps recognition, authorization, action and wake scheduling separate:

- `dom_contract.js` recognizes only the captured timeout shape and only when it is the latest rendered conversation turn;
- `exhaustion_guard.js` observes the DOM, reports the typed assistant error and never invents a replacement user message;
- `worker_transport.js` owns exact URL/top-frame transport trust, normal content protocol readiness, independent assistant-guard readiness and live timeout preflight;
- `worker_assistant_errors.js` requires the exact preferred delivery tab, validates Bridge ownership, serializes durable attempt accounting and authorizes each click against the current binding revision/generation;
- `worker_delivery.js` refuses a fresh wake while the live guard still reports an unresolved timeout;
- `worker_conversations.js` clears old retry accounting on explicit rebind/remove/re-add lifecycle boundaries;
- the recovery action is ChatGPT's existing Retry button, so the original user message is retried instead of duplicated.

Immediately before each click the guard asks the worker for authorization and then revalidates URL, triggering-user identity, current timeout snapshot, generation state and Retry-button usability. The worker independently rechecks Master/enabled state, binding revision, conversation generation and exact preferred tab.

The worker stores retry accounting separately in bounded Chrome local storage. The effective retry key includes conversation URL, binding revision, triggering user identity and error kind; recreating the assistant error node does not reset the budget. MV3 service-worker restart therefore resumes the existing attempt count.

## Retry policy

The candidate uses three attempts with increasing delays:

```text
attempt 1: 1.5 s
attempt 2: 5 s
attempt 3: 15 s
```

After the third failed Retry, the next observation marks `assistant_retry_exhausted`, disables that conversation and clears its alarm. There is no fourth automatic click.

If the error belongs to a normal operator-authored message rather than a Bridge hard-binding prompt, it is detected as `assistant_delivery_timeout_unowned`, but Bridge does not click Retry automatically.

If ChatGPT reuses the same error DOM node during Retry, guard v3 applies an 8-second minimum recheck grace and then continues waiting through any still-active generation using the normal DOM/periodic scan loop. Eight seconds is not treated as a completion deadline. The unchanged timeout may consume the next attempt only after generation has actually stopped.

A retained timeout card behind any newer user or assistant turn is stale evidence and is ignored.

## Wake-overlap gate

Before any scheduled or manual Bridge wake, the worker probes the live assistant guard. If the recoverable timeout is still current, the wake returns:

```text
assistant_recovery_pending
```

No new user prompt is submitted. The preflight also re-arms the exact preferred tab's recovery scanner when a previous authorization was cancelled by a Master/lifecycle transition. Once the live DOM no longer reports that timeout as current, ordinary wake delivery may continue.

This live preflight prevents a one-minute/busy-retry alarm or manual `Run now` from layering another Bridge prompt over an unresolved assistant failure.

## Protocol/update behavior

Chat Bridge candidate version is `0.5.10`. Ordinary content protocol remains v7 because normal submission semantics did not change. Assistant timeout/exhaustion observation has its own guard protocol v3.

Worker activation now probes both protocols for already-open configured tabs. A tab with current `content.js` but a stale assistant guard is no longer treated as fully ready: only the stale guard scripts are replaced and readiness is probed again. This closes the extension-reload case where old timeout behavior could otherwise remain alive in an open ChatGPT tab.

## Statuses

The candidate exposes distinct diagnostics instead of overloading `delivery_unconfirmed`:

```text
assistant_delivery_timeout
assistant_delivery_timeout_unowned
assistant_retry_1
assistant_retry_2
assistant_retry_3
assistant_recovery_pending
assistant_retry_exhausted
```

Existing conversation-length exhaustion remains a separate terminal path.

## Verification surface

Focused Node coverage includes:

- exact captured DOM matching and negative lookalikes;
- latest-turn/stale-card rejection;
- Bridge-owned versus operator-owned messages;
- exact preferred-tab rejection for duplicate tabs;
- binding-revision/generation context rejection between report and Retry;
- retry delay progression and serialized durable accounting;
- MV3 service-worker restart persistence;
- retry-budget reset across rebind/remove/re-add;
- stale assistant-guard replacement on worker activation;
- unresolved-timeout wake gating and recovery after live DOM clears;
- fail-closed three-attempt exhaustion.

The browser profile tests are isolated and offline but load the **real unpacked extension**. One smoke reproduces the captured timeout, lets Bridge click Retry and asserts there is still exactly one submitted user message. A second resilience smoke proves that a stale timeout behind a newer answer is never clicked and that the same timeout node can survive a generation longer than eight seconds, receive exactly three bounded Retry clicks and finish fail-closed without duplicating the user turn.

The full scenario/race matrix and live-only unknowns are recorded in `docs/superchat/DELIVERY_TIMEOUT_PRELIVE_AUDIT.md`.

## Release boundary

This branch is a candidate, not production. Advancing `main` still requires an explicit release decision, final exact-head CI/browser evidence and release metadata/version synchronization. A browser-only candidate does not require restarting the Local Agent daemon during development/review.

No sandbox can certify the current ChatGPT production DOM or server Retry semantics. The exact final candidate should therefore receive one controlled live browser smoke before `main` is advanced, with Master disabled until the observed invariants pass.
