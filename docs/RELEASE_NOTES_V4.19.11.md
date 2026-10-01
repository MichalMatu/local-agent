# Local Agent 4.19.11

## Summary

Local Agent 4.19.11 is the checkpoint hardening release after the Chat Bridge migration from assistant-DOM pacing to GitHub `conversation_controls`. Chat Bridge advances to 0.6.2 while runtime schema 3, content protocol v13 and assistant guard v8 remain unchanged.

## Terminal safety repair

The audit found a cross-contract regression in GitHub drift repair. After a desired generation had been applied, local `conversation_exhausted` or `assistant_retry_exhausted` handling disables the chat and advances local generation. Reconciliation could then interpret that deliberate local safety transition as drift and restore `enabled=true` from remote desired state.

The repaired ownership boundary is explicit:

- `conversation_exhausted` remains terminal for the same hard binding and survives both same-generation drift repair and later pacing generations;
- `assistant_retry_exhausted` survives reconciliation of the already-applied generation, while a strictly newer GitHub generation is treated as an explicit recovery decision;
- preserved terminal state clears conversation alarms and updates applied GitHub-control evidence so reconciliation does not loop;
- manual `Run now` cannot bypass confirmed conversation exhaustion.

Focused regression coverage exercises same/new-generation reconciliation, alarm state, applied-journal state and manual delivery.

## Release engineering hardening

- CI coverage now fails below 70% instead of merely printing the report.
- `actions/checkout`, `actions/setup-python` and `actions/setup-node` are pinned to immutable commit revisions rather than mutable major-version tags.
- The checkpoint audit re-evaluated historical BUG-001 against the shipped guarded-entrypoint orphaned lease recovery introduced in v4.18.5; current release review treats that original repository-lease incident as repaired rather than an unresolved runtime blocker.

## Unchanged contracts

This release does not change task schema, repository hard binding, executor semantics, scheduler/resource classification, production worker count, MCP policy, runtime schema, content protocol or assistant guard protocol. `local-agent` remains execution-disabled in the planner catalog.

## Release gate

The exact candidate passed the canonical CI matrix and the bounded production-shaped live browser gate. The live GitHub desired-state path was exercised with a short one-minute interval and the managed conversation was returned to PAUSED (enabled=false, next_wake_at=null).

The remaining release actions are administrative and deliberately explicit: merge PR #122 into main, tag the released commit v4.19.11, verify the installed runtime from main and remove the obsolete checkpoint branch after production proof. Until those actions complete, the deployed production release remains v4.19.10 / Chat Bridge 0.6.1.
