# ChatGPT DOM contract for Chat Bridge

This document records the **current implemented compatibility contract** used by Local Agent Chat Bridge. It is intentionally narrow: selectors are evidence, not ChatGPT product guarantees, and every unsupported page shape must fail closed.

Historical release notes under `docs/RELEASE_NOTES_*.md` describe earlier renderer assumptions. Do not use an older release note as the current DOM contract.

## Current production baseline

```text
Local Agent:      v4.19.8
Chat Bridge:      0.5.18
content protocol: v13
assistant guard:  v8
```

The field evidence that led to this contract is summarized in `CHAT_BRIDGE_HANDOFF_2026-09-29.md`.

## Logical turn discovery

Supported explicit role families:

```text
assistant legacy: [data-message-author-role="assistant"]
assistant current: [data-conversation-role="assistant"]
user legacy:      [data-message-author-role="user"]
user current:     [data-user-message-bubble]
logical turn:     [data-turn-key]
```

Bridge collects compatible explicit role nodes in document order and deduplicates nested representations by the surrounding `data-turn-key` when present.

### Assistant grouped-turn fallback

Live inspection on 2026-09-29 confirmed an assistant-only renderer variant where a `data-turn-key` contains assistant paragraph content and action controls but exposes **neither** a user bubble **nor** an explicit assistant-role marker.

Therefore grouped assistant fallback must **not** require a user bubble.

For assistant LAB discovery Bridge:

1. clones the logical `data-turn-key` turn;
2. removes recognized user bubbles;
3. removes grouped action controls (`button`, `[role="button"]`);
4. treats the turn as assistant content only if residual text is non-empty.

This preserves both sides of the boundary:

- assistant-only grouped turns remain visible to the scanner;
- user-only grouped shells collapse to empty residual assistant text and cannot execute assistant controls.

When an explicit assistant node and grouped fallback refer to the same turn, keep the explicit node. A newer grouped-only assistant turn may still supersede an older explicit turn by document order.

`data-turn-key` is only a DOM turn identity fallback. It is never a Bridge conversation id, repository id or agent binding.

## Submitted-user confirmation

The same combined user selector contract is used to confirm that a just-submitted Bridge prompt appears as the newest user turn. Do not infer successful delivery solely from a click or form submission attempt.

## Assistant generation state

Generation is considered active only when a visible ChatGPT Stop control is present:

```text
button[data-testid="stop-button"]
button[data-testid="composer-stop-button"]
```

External recovery/reload and managed diagnostic-browser stop must fail closed while generation is active unless the operator explicitly requests the emergency force path.

## Conversation-length exhaustion

A conversation is exhausted only when the latest supported assistant turn contains:

- `.text-token-text-error`;
- normalized text containing `You've reached the maximum length for this conversation`;
- one descendant `button` whose normalized visible text is exactly `Start new chat`.

Generated CSS classes, SVG ids, exact nesting depth and complete sentence equality are not part of the contract.

When detected, Bridge records `conversation_exhausted`, disables that conversation and clears its alarm. Rollover into a new ChatGPT conversation is **not** implemented by this DOM contract and is outside the current runtime behavior.

## Recoverable assistant terminal errors

Bridge currently recognizes exactly two post-submission assistant terminal errors:

```text
Message delivery timed out. Please try again.
Resume stream unavailable
```

A recoverable error requires all of the following:

- the latest rendered conversation turn across explicit role families and the bounded grouped-turn fallback is the assistant/error turn;
- that turn contains `.text-token-text-error`;
- normalized error text contains one of the two recognized strings above;
- the error contains `button[data-testid="regenerate-thread-error-button"]`, or as a bounded compatibility fallback a descendant button whose normalized visible text is exactly `Retry`;
- the triggering user turn still exists and is the latest user turn.

Unknown Retry-looking error cards fail closed.

A matching error followed by any newer user or assistant turn is stale evidence and must not be retried.

## Retry authorization boundary

Detection is not authorization.

Automatic native Retry requires the worker to revalidate:

- exact preferred tab;
- exact normalized conversation URL;
- current binding revision;
- current conversation generation;
- Master enabled state;
- conversation enabled state;
- Bridge ownership of the triggering user message.

Bridge ownership means the triggering user message begins with the exact current Bridge binding envelope/policy. A terminal error following a normal operator-authored prompt may be reported diagnostically but must not be clicked automatically.

Immediately before every click the content guard rechecks the same live error snapshot, generation state and Retry-button usability. Bridge clicks ChatGPT's native Retry button; it never resubmits the already-accepted user prompt for these error classes.

## Retry identity and budget

Assistant DOM ids may change across rehydration and are not durable retry identity.

The durable retry key is scoped to:

- conversation;
- binding revision;
- recoverable error kind;
- deterministic triggering-user identity derived from transcript position plus user text.

The authorized retry budget is:

```text
attempt 1: 1.5 s
attempt 2: 5 s
attempt 3: 15 s
```

If ChatGPT reuses the same error node while Retry is generating, the guard waits through generation and re-evaluates after generation stops. After the third unsuccessful Retry, Bridge records `assistant_retry_exhausted`, disables only that conversation and clears its alarm.

Normal wake delivery is blocked as `assistant_recovery_pending` while a recognized current error remains unresolved.

## Binding semantics relevant to DOM handling

One ChatGPT conversation has one **current Bridge binding revision**. An explicit `ADD`/`REBIND` may create a new binding revision; a wake emitted under a revision carries that exact immutable envelope.

`planner_scope=multirepo` does not make the DOM binding ambiguous. The canonical `host-ops` conversation remains bound to `host-ops` while the planner may target other repositories from the validated runtime catalog; any Local Agent task still uses the exact binding of its target repository.

Do not infer repository identity from DOM ids, ChatGPT text, model answers or renderer structure.

## What is intentionally not part of this contract

Do not depend on:

- Tailwind/generated CSS class names;
- generated SVG ids;
- exact element depth;
- a user bubble being present inside every assistant logical turn;
- any one assistant role family existing globally on the page;
- `data-message-id` remaining stable across rehydration;
- a page reload refreshing an unpacked MV3 service worker;
- speculative automatic cross-conversation rollover.

New renderer variants must be added only from bounded live evidence plus focused DOM tests and real-extension browser regression coverage.
