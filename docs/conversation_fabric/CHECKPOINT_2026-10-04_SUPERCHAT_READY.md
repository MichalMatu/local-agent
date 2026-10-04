# Checkpoint — ready for bounded live Superchat acceptance

> **HISTORICAL SNAPSHOT — ACCEPTANCE COMPLETED LATER ON 2026-10-04**
>
> This checkpoint records the state immediately before the first bounded live Superchat acceptance. It is not current operating guidance. Statements below about Chat Bridge `0.8.1`, `local-agent` being execution-disabled, deferred dedupe behavior, or acceptance still being “next” were superseded later the same day. For current behavior read `../CURRENT_HANDOFF.md`, `../GOLDEN_STANDARD.md`, `README.md` and `CURRENT_PLAN.md`.

Date: 2026-10-04

## Immutable anchors at this checkpoint

- Local Agent release line: `4.20.6`.
- Chat Bridge: `0.8.1`.
- immutable tag `v4.20.6` -> release commit `48eb9d8b6c26a9dfb317906d5099acabce8719c8`.
- queue-dedupe release PR: `#138`, merged.
- child-browser readiness PR: `#135`, final candidate `97e9e8419bdb83084a300f007bf0e7d21dd1f29b`, exact-head CI 5/5 green, squash-merged as code checkpoint `e4b3da908cfac61bb11cd0e4182b7d9e7c42d5b8`.
- superseded docs PR `#137`: closed without merge.

Current `main` may be later because this checkpoint/documentation is committed after the code checkpoint. Always read it fresh.

## Verified code state at this checkpoint

The self-diagnostic and follow-up cleanup established:

- parent scheduler/routing/process boundaries have no known P0/P1 blocker;
- Local Agent production parallel execution has deterministic queue dedupe;
- child chats remain reasoning-only;
- target execution still requires exact canonical repository binding;
- child auth/session readiness is probed independently of composer DOM readiness;
- composer readiness remains bounded at pre-submit time;
- exact refreshed child repair passed `test`, `python-314`, `coverage`, `macos-smoke` and `bridge-browser`.

## Operational rest state at this checkpoint

At the end of the self-diagnostic, all known managed Chat Bridge `conversation_controls` were disabled with no scheduled wake. `local-agent` was execution-disabled as a normal task target at that checkpoint. Conversation Operator intake was treated as explicit live configuration for the bounded proof.

This is historical state only. The current canonical runtime catalog is authoritative for `execution_enabled` and binding admission.

## Branch policy

Permanent branches are only:

- `main`;
- `chat-bridge-state`;
- `operator-control`.

`work/*`, historical `develop/*` and `archive/*` refs are disposable once their evidence is merged/closed. They are never source of truth.

## Known deferred issue at this checkpoint

Recent-completion dedupe then recorded a bounded completion receipt after a task result was successfully published even if the underlying task result was failed. This was a historical deferred concern. Current dedupe semantics and recovery must be read from current source and `../GOLDEN_STANDARD.md`, not inferred from this checkpoint.

## Historical readiness verdict

**READY FOR BOUNDED LIVE ACCEPTANCE.**

That acceptance was subsequently completed and the production model moved to same-browser Chat Bridge `0.8.3` with durable Conversation Fabric recovery and later runtime/Fabric hardening. Current work is the stronger restart/reload/no-replay acceptance described in `CURRENT_PLAN.md`.
