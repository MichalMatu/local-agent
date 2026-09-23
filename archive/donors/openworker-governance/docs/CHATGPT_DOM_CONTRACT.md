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

## Current bridge behavior

Chat Bridge detects this state before attempting another wake delivery. A detected exhausted conversation is terminal for the current conversation URL: the bridge records `conversation_exhausted`, disables that conversation, and clears its scheduled alarm. It does not repeatedly type into a dead composer and does not automatically change repository binding.

This is intentionally conservative. The existing hard-binding rule still applies:

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
