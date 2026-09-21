# ChatGPT delivery-timeout recovery research

Status: branch-only investigation. No production runtime, Local Agent daemon, or installed Chat Bridge restart is required by this work.

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

Observed stable signals, ordered by usefulness:

1. assistant message boundary: `[data-message-author-role="assistant"]`;
2. error surface: `.text-token-text-error`;
3. exact recoverable error text: `Message delivery timed out. Please try again.`;
4. explicit retry control: `button[data-testid="regenerate-thread-error-button"]`;
5. fallback button text: `Retry`;
6. assistant message identity from `data-message-id`.

The saved page proves that the timeout is represented as an assistant message, not as a missing DOM message or a composer-send failure.

## Why current Bridge misses it

The current delivery lifecycle considers a wake `sent` as soon as the submitted user message appears in the DOM. That is intentionally only transport confirmation. A later ChatGPT response failure is outside `worker_delivery.js` delivery confirmation.

`content.js` then sees the timeout element through `latestAssistantMessage()`. Because the text is not a LAB control, `scanLatestAssistantControl()` records the assistant signature as scanned and takes no recovery action.

This means the existing `delivery_unconfirmed` state does not cover this failure. The user message was confirmed; assistant generation failed afterwards.

## Existing architecture that should be reused

The repository already has the correct pattern for DOM-level terminal state detection:

- `dom_contract.js` owns stable ChatGPT DOM recognition;
- `exhaustion_guard.js` observes the document with bounded deduplication;
- `worker_transport.js` validates content-script reports against extension id, top frame, exact normalized conversation URL, and stored conversation state;
- `worker_events.js` routes content-originated reports;
- browser smoke tests use an offline ChatGPT fixture and the real unpacked extension.

The first branch slice adds only a pure DOM contract for this captured recoverable timeout. It deliberately does not click Retry yet.

## Recommended recovery design

Detection and action should remain separate.

The detector should emit a typed result such as:

```text
kind = message_delivery_timeout
conversation URL
assistant message identity
stable signature
retry control present
```

The recovery path should be bounded and fail closed:

- act only on an exact recognized error plus an explicit Retry control;
- never synthesize another wake/user message for this case, because that would duplicate the prompt rather than retry the failed assistant generation;
- prefer the existing ChatGPT Retry control for recovery;
- deduplicate by conversation plus triggering user-message identity/error kind, not only assistant error message id, because a retry may replace the error node;
- use bounded exponential delay and a hard retry cap;
- stop immediately if the conversation URL changes, generation starts, a new user message appears, the Retry control disappears, or operator/Bridge state disables the chat;
- expose a distinct status such as `assistant_delivery_timeout` / `assistant_retry_exhausted` instead of reusing `delivery_unconfirmed`;
- add unit coverage, worker sender-validation/race coverage, and an offline Chromium case before considering release.

## Open implementation question

There are two safe milestones:

1. detection/reporting only, which makes the failure visible to Bridge diagnostics without mutating the ChatGPT page;
2. bounded automatic Retry clicking after worker authorization.

Milestone 1 is lower risk and is the current branch starting point. Milestone 2 should be implemented only with explicit attempt accounting and browser-level evidence that a retry does not create duplicate user messages.
