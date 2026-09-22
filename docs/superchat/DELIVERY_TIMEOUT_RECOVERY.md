# ChatGPT delivery-timeout recovery

Status: implemented and validated on `work/chat-delivery-timeout-detection`. Production `main`, the installed Local Agent daemon and the installed Chat Bridge were not changed or restarted during this work.

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

Stable signals used by the detector are the assistant message boundary, `.text-token-text-error`, the exact timeout text, the explicit `regenerate-thread-error-button`, fallback `Retry` button text and assistant message identity.

The capture proves that this failure occurs after the user message has already been accepted. It is therefore not the existing `delivery_unconfirmed` transport case.

## Why the previous Bridge missed it

Normal delivery is considered `sent` once the exact submitted user message appears in the DOM. That is intentionally transport confirmation only. A later ChatGPT response-generation failure occurs after `worker_delivery.js` has finished.

The assistant-control scanner then sees the timeout message, but because it contains no LAB command it records the assistant content as scanned and takes no recovery action.

## Implemented recovery path

The branch keeps DOM recognition, authorization and action separate:

- `dom_contract.js` recognizes only the captured recoverable timeout shape;
- `exhaustion_guard.js` observes the DOM, reports a typed assistant error and never invents a replacement user message;
- `worker_assistant_errors.js` validates the sender through the existing exact-tab/exact-conversation trust boundary;
- automatic recovery is allowed only when the triggering user message begins with the exact Bridge hard-binding envelope and policy for the configured conversation;
- immediately before each click the guard asks the worker for authorization again, then revalidates URL, user identity, error identity, generation state and Retry-button usability;
- the recovery action is ChatGPT's existing `Retry` button, so the original user message is retried instead of duplicated.

The worker stores retry accounting separately in bounded Chrome local storage. Attempts are keyed by conversation plus triggering user-message identity plus error kind, so a recreated assistant error node does not reset the budget.

## Retry policy

The current candidate uses three attempts with increasing delays:

```text
attempt 1: 1.5 s
attempt 2: 5 s
attempt 3: 15 s
```

After the third failed Retry, the next observation marks `assistant_retry_exhausted`, disables that conversation and clears its alarm. This is fail-closed: Bridge does not send a fresh wake on top of the failed user message.

If the error belongs to a normal operator-authored message rather than a Bridge hard-binding prompt, it is still detected as `assistant_delivery_timeout_unowned`, but Bridge does not click Retry automatically.

If ChatGPT reuses the same error DOM node during a Retry, a bounded watchdog waits for generation to stop and then permits the unchanged error to be reported again. This prevents DOM identity reuse from bypassing the durable three-attempt cap or stalling recovery indefinitely.

## Statuses

The candidate exposes distinct diagnostics instead of overloading `delivery_unconfirmed`:

```text
assistant_delivery_timeout
assistant_delivery_timeout_unowned
assistant_retry_1
assistant_retry_2
assistant_retry_3
assistant_retry_exhausted
```

Existing conversation-length exhaustion remains a separate terminal path.

## Verification evidence

Unit coverage includes exact DOM matching, sender/conversation rejection, Bridge-owned versus operator-owned messages, retry delay progression, durable attempt accounting and fail-closed exhaustion.

The browser smoke uses an isolated offline Chromium profile with the real unpacked extension. Its fixture submits one Bridge wake, renders the captured timeout structure, lets Bridge click Retry and asserts that there is still exactly one user submission. The recovered assistant response is then observed.

GitHub Actions run `35672263362` for candidate `10fa71c9a274e30cb390221f6f2bac52ea93b403` passed all five jobs: normal tests, coverage, Python 3.14, macOS smoke and browser smoke. The browser log contains:

```text
PASS: assistant delivery timeout is detected and recovered with one bounded Retry click
```

The later watchdog hardening remains branch-only and requires the same exact-head CI/browser verification before any release decision.

## Release boundary

This branch is a candidate, not production. Advancing `main` should still require an explicit release decision, current release metadata/version synchronization and a final exact-head CI/browser pass. No Local Agent daemon restart is required to develop or review this branch.

The final branch head after watchdog hardening and this validation note is the exact candidate that must be accepted by CI; no production update is implied by that validation.
