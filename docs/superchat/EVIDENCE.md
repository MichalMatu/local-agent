# Superchat evidence inventory

This file records concrete artifacts available for implementation and testing. It is not a design document.

## 2026-09-06 — Maximum-length conversation

### Captured DOM fragment

Available evidence contains the terminal assistant message with:

```text
[data-message-author-role="assistant"]
  -> .text-token-text-error
  -> text containing:
     "You've reached the maximum length for this conversation"
  -> descendant button with visible text:
     "Start new chat"
```

The message also exposes a `data-message-id`.

This evidence is sufficient for the current terminal exhaustion detector and is already represented by:

- `docs/CHATGPT_DOM_CONTRACT.md`;
- `chat_bridge/dom_contract.js`;
- `chat_bridge/exhaustion_guard.js`.

## Evidence still needed for automatic rollover

The hard-exhaustion detector is sufficiently evidenced. Automatic replacement-chat creation still needs live evidence for the following states.

### New-chat landing page

Capture:

- URL before a concrete conversation id exists;
- stable composer selectors;
- send button selectors/state;
- whether `Start new chat` and directly opening `https://chatgpt.com/` produce equivalent usable surfaces.

### First bootstrap submission

Capture before and after submitting one test message:

- URL before submit;
- DOM user-message count/text after submit;
- exact moment a concrete `/c/<id>` URL appears;
- whether URL assignment can precede visible user-message confirmation;
- composer state after accepted submit.

### Ambiguous submit/restart case

Create a controlled test where the service worker loses its response immediately after submit. Determine which evidence can prove whether the message was accepted without submitting it twice.

Candidate evidence:

- tab id survives;
- tab URL is now concrete `/c/<id>`;
- first user message contains the operation marker;
- composer is empty;
- conversation page contains exactly one bootstrap user message.

### Start-new-chat button behavior

From a real exhausted conversation, record what happens after clicking the observed `Start new chat` button:

- resulting URL;
- whether the old tab is reused;
- whether browser history contains the old conversation;
- when the new composer becomes writable;
- whether the old conversation remains accessible by its original URL.

## Fixture strategy

Recommended committed fixtures:

```text
tests/fixtures/chat_bridge/
  exhausted_conversation.html
  exhausted_missing_button.html
  exhausted_wrong_text.html
  exhausted_ambiguous_buttons.html
  new_chat_ready.html              # after live evidence is captured
```

Fixtures should contain only the minimum markup needed by the DOM contract. Remove conversation content, account data, ids that are not required for behavior, analytics markup and downloaded application assets.
