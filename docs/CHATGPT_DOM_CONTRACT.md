# ChatGPT DOM contract for Chat Bridge

This document records observed ChatGPT DOM structures that Local Agent may use as browser-integration signals. Treat these selectors as compatibility contracts, not product guarantees: every selector must fail closed when the page shape changes.

## Conversation length exhaustion

Observed live ChatGPT markup on 2026-09-06 when a conversation reaches its maximum length:

```html
<div
  data-message-author-role="assistant"
  data-message-id="<assistant-message-id>"
  class="..."
>
  <div class="text-token-text-error ...">
    ...
    <p>
      You've reached the maximum length for this conversation, but you can keep talking by starting a new chat.
    </p>
    ...
    <button class="btn ... btn-secondary">
      <div class="...">
        <svg ...></svg>
        Start new chat
      </div>
    </button>
  </div>
</div>
```

The useful signals are deliberately structural and textual rather than generated class strings:

- message root: `[data-message-author-role="assistant"]`;
- error container inside that message: `.text-token-text-error`;
- normalized error text contains `You've reached the maximum length for this conversation`;
- a descendant `button` has normalized visible text exactly `Start new chat`;
- `data-message-id` is useful as an observed assistant-message identity but must not be interpreted as a repository or bridge identity.

Do not depend on Tailwind utility classes, SVG sprite ids, generated CSS hashes, element depth, or the complete sentence remaining byte-for-byte identical.

## Assistant message-delivery timeout

Observed live ChatGPT markup captured on 2026-09-22 after ChatGPT had already accepted the user message but failed to produce/deliver the assistant answer:

```html
<div data-message-author-role="assistant" data-message-id="<assistant-message-id>">
  <div class="... text-token-text-error ...">
    <p>Message delivery timed out. Please try again.</p>
    <button data-testid="regenerate-thread-error-button">Retry</button>
  </div>
</div>
```

The recoverable-timeout detector deliberately requires all of these conditions:

- the **latest rendered conversation turn** matching `[data-message-author-role]` is an assistant turn;
- that latest turn contains `.text-token-text-error`;
- normalized error text contains `Message delivery timed out. Please try again.`;
- the error contains `button[data-testid="regenerate-thread-error-button"]`, or as a compatibility fallback a descendant button whose normalized visible text is exactly `Retry`;
- the triggering user turn still exists and is the latest user turn.

A matching timeout card that is followed by any newer rendered conversation turn is stale evidence and must not be retried. This prevents an old retained error node from being attached to a later user/assistant exchange.

The content guard may use the assistant DOM identity to distinguish the currently rendered error card, but the durable retry budget is keyed to the conversation, binding revision, recoverable error kind and a deterministic triggering-user identity derived from transcript position plus user text. It must not depend on a ChatGPT DOM message id remaining stable across page rehydration.

Automatic Retry is narrower than detection. The worker authorizes a click only when the triggering user text begins with the exact hard-binding Bridge envelope/policy for that configured conversation. A timeout after a normal operator-authored user message is reported diagnostically but never clicked automatically.

Immediately before every click the content guard rechecks the exact conversation URL, triggering-user identity, timeout snapshot, assistant generation state and Retry-button usability. The action is ChatGPT's own Retry button; Bridge never creates a replacement user message for this failure mode.

Retry accounting is durable and bounded to three authorized clicks with 1.5 s, 5 s and 15 s delays. If ChatGPT reuses the same timeout DOM node while Retry is generating, the guard waits through generation and only re-evaluates the unchanged error after generation has stopped. After the third unsuccessful Retry the worker records `assistant_retry_exhausted`, disables that conversation and clears its alarm instead of layering a new wake over the failed turn.

## Current bridge behavior

Chat Bridge detects conversation-length exhaustion before attempting another wake delivery. A detected exhausted conversation is terminal for the current conversation URL: the bridge records `conversation_exhausted`, disables that conversation, and clears its scheduled alarm. It does not repeatedly type into a dead composer and does not automatically change repository binding.

Assistant message-delivery timeout is a separate post-submission recovery path. It does not reuse `delivery_unconfirmed`: normal delivery is already considered transport-confirmed once the exact submitted user message appears in the DOM. A later assistant-side timeout is therefore detected and recovered independently.

The existing hard-binding rule still applies:

```text
one ChatGPT conversation == one immutable agent_binding == one repository
```

## Future supervisor / "superchat" rollover

A higher-level supervisor can later use the same DOM contract to continue work across ChatGPT conversation boundaries. The expected rollover transaction should be explicit and stateful:

1. Detect the exhausted assistant error using the contract above.
2. Capture the old bridge conversation state: repository id, repository name, `agent_binding`, active goal metadata, pacing, and last verified evidence pointers.
3. Click the exact descendant button whose normalized visible text is `Start new chat`.
4. Wait for the new-chat UI to become ready. A root/new-chat page does not yet have a stable `/c/<id>` conversation URL.
5. Inject one bootstrap/continuation prompt containing the old immutable repository binding plus a bounded handoff summary of the active goal and exact evidence.
6. Wait until ChatGPT assigns the new concrete `/c/<new-id>` URL after the first submitted message.
7. Create a new bridge conversation record for that new URL with the same repository binding, a fresh bridge conversation id, a fresh assistant baseline, and `bootstrapPending=true` or equivalent rollover state.
8. Leave the exhausted old conversation disabled and immutable for audit/history. Never rewrite its URL into the new conversation.
9. Resume scheduled wakes only after the new concrete URL and binding record are persisted.

The superchat layer must preserve repository identity; rollover changes the ChatGPT conversation identity, not the Local Agent repository identity.

## Failure policy for future rollover

Automatic rollover must fail closed when any of these are ambiguous: no exact Start new chat button, multiple candidate buttons in the exhausted message, navigation did not reach a new-chat composer, the first message was not confirmed, the new `/c/<id>` URL was not observed, or the stored binding changed during the transaction.

Do not infer a new repository from the model's answer. Do not delete the old conversation record until the replacement conversation is durably registered. A recoverable supervisor should persist an explicit rollover journal before clicking so a browser/service-worker restart cannot silently duplicate or lose the handoff.
