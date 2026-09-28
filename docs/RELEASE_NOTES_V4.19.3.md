# Local Agent 4.19.3 / Chat Bridge 0.5.12

## Summary

Repair live Chat Bridge assistant/operator control discovery after ChatGPT changed its rendered conversation-turn attributes.

## Live failure evidence

On 2026-09-28 the dedicated production ChatGPT tab had zero matches for the legacy `[data-message-author-role="assistant"]`, `[data-message-author-role="user"]`, `article/section[data-testid^="conversation-turn"]` and `[data-turn]` selectors. The same exact page exposed three `[data-conversation-role="assistant"]` nodes, four `[data-user-message-bubble]` nodes and five `[data-turn-key]` nodes. Because `content.js` read only the legacy role family, valid assistant controls such as `ADD` and `STATUS` were never observed.

## Repair

- Keep the legacy message-role selectors as the preferred compatibility family.
- Fall back to `[data-conversation-role="assistant"]` and `[data-user-message-bubble]` when the legacy family is absent.
- Use the nearest `[data-turn-key]` only as a stable DOM identity fallback.
- Apply the same compatibility contract to assistant timeout/exhaustion detection.
- Advance content protocol v7 -> v8 and guard protocol v3 -> v4 so worker activation replaces already-open stale content/guard scripts without requiring a normal page reload.

Repository identity, planner scope, Local Agent task binding, scheduler/resource semantics and executor behavior are unchanged.

## Verification

The release requires focused DOM/control tests, the real-extension browser profile, the canonical full verifier/CI matrix and live post-deploy proof that an unbound conversation can execute assistant `ADD=host-ops` followed by `STATUS` on the exact dedicated tab.
