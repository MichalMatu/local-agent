# Local Agent 4.19.4

Chat Bridge 0.5.13 / content protocol v9 / assistant guard v4.

## Summary

This follow-up fixes mixed ChatGPT DOM rollouts where legacy and current role markers coexist in one conversation. The 4.19.3 compatibility fallback chose the legacy role family whenever any legacy node existed, which could hide a later current-family turn and produce stale assistant controls or false `delivery_unconfirmed` results.

## Bridge behavior

- Collect both supported assistant/user selector families in one document-ordered query.
- Deduplicate nested representations that belong to the same surrounding `data-turn-key` turn.
- Treat the document-latest logical turn as authoritative regardless of which role family rendered it.
- Prefer `data-turn-key` as the stable DOM identity when it exists.
- Apply the same ordering rule to submitted-user confirmation, assistant/operator control discovery, conversation exhaustion and assistant timeout recovery.

## Upgrade behavior

Chat Bridge advances from 0.5.12 to 0.5.13 and content protocol advances from v8 to v9. Worker-owned protocol refresh therefore reinjects the repaired content script into reachable already-open ChatGPT tabs. Assistant timeout/exhaustion guard protocol remains v4 because its transport boundary is unchanged.

Repository binding, planner scope, scheduler/resource semantics and executor/task contracts do not change.
