# Local Agent 4.19.5

Chat Bridge 0.5.14 / content protocol v10 / assistant guard v6.

## Summary

Live production inspection on 2026-09-28 showed a further ChatGPT renderer variant with a healthy composer, five `data-turn-key` exchange containers and five `data-user-message-bubble` nodes, but zero legacy `data-message-author-role="assistant"` and zero `data-conversation-role="assistant"` nodes. Chat Bridge 0.5.13 was current and fingerprint-clean after an exact-profile restart, proving the remaining failure was DOM discovery rather than stale extension code.

## Grouped-turn fallback

When no explicit assistant-role nodes exist, the content script treats `data-turn-key` containers that contain a recognized user bubble as logical exchanges. Before assistant LAB parsing it clones the selected exchange and removes every recognized user bubble from the clone. Only the remaining text is eligible for the assistant namespace. A user-only turn therefore produces no assistant control, even when the user text contains a syntactically valid `[LAB:*]` marker.

Structured timeout and conversation-exhaustion detection use the same grouped-turn fallback. They still require the existing typed error DOM and action button, so ordinary user text cannot synthesize a recoverable assistant error.

## Upgrade behavior

Chat Bridge advances from 0.5.13 to 0.5.14, content protocol from v9 to v10 and assistant guard protocol from v5 to v6. These bumps force worker-owned replacement of both `content.js` and the guard-captured `dom_contract.js` on reachable already-open tabs. Repository binding, scheduler/resource semantics and executor admission do not change.

## Regression coverage

The isolated real-extension browser fixture includes a grouped turn with assistant `[LAB:RESUME]` and a later competing user `[LAB:PAUSE]`; only RESUME may execute. A subsequent user-only grouped turn containing `[LAB:STOP]` must leave conversation state unchanged.
