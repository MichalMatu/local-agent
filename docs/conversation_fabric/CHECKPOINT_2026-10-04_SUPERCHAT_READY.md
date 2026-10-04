# Checkpoint — ready for bounded live Superchat acceptance

Date: 2026-10-04

## Immutable anchors

- Local Agent release line: `4.20.6`.
- Chat Bridge: `0.8.1`.
- immutable tag `v4.20.6` -> release commit `48eb9d8b6c26a9dfb317906d5099acabce8719c8`.
- queue-dedupe release PR: `#138`, merged.
- child-browser readiness PR: `#135`, final candidate `97e9e8419bdb83084a300f007bf0e7d21dd1f29b`, exact-head CI 5/5 green, squash-merged as code checkpoint `e4b3da908cfac61bb11cd0e4182b7d9e7c42d5b8`.
- superseded docs PR `#137`: closed without merge.

Current `main` may be later because this checkpoint/documentation is committed after the code checkpoint. Always read it fresh.

## Verified code state

The self-diagnostic and follow-up cleanup established:

- parent scheduler/routing/process boundaries have no known P0/P1 blocker;
- Local Agent production parallel execution has deterministic queue dedupe;
- child chats remain reasoning-only;
- target execution still requires exact canonical repository binding;
- child auth/session readiness is probed independently of composer DOM readiness;
- composer readiness remains bounded at pre-submit time;
- exact refreshed child repair passed `test`, `python-314`, `coverage`, `macos-smoke` and `bridge-browser`.

## Operational rest state

At the end of the self-diagnostic, all known managed Chat Bridge `conversation_controls` were disabled with no scheduled wake. `local-agent` is execution-disabled as a normal task target. Conversation Operator intake must be treated as explicit live configuration: verify fresh before use, enable only through the supported path for the bounded proof, and do not leave it unintentionally active afterward.

## Branch policy

Permanent branches are only:

- `main`;
- `chat-bridge-state`;
- `operator-control`.

`work/*`, historical `develop/*` and `archive/*` refs are disposable once their evidence is merged/closed. They are never source of truth.

## Known deferred issue

Recent-completion dedupe currently records a bounded completion receipt after a task result is successfully published even if the underlying task result is failed. Reusing the same explicit `dedupe_key` for a materially changed correction could therefore be suppressed within the TTL. For the live acceptance, never reuse an old intent key for a changed corrective plan. Harden this later without weakening duplicate suppression.

## Readiness verdict

**READY FOR BOUNDED LIVE ACCEPTANCE.**

The next chat must prove the user-visible architecture rather than perform another broad self-audit: one Superchat parent delegates real reasoning to child chats on real code, observes their outputs, synthesizes the decision and remains the only authority that may request target-bound Local Agent execution.
