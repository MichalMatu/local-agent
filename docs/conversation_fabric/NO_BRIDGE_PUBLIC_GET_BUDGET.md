# No-Bridge anonymous public GET session budget (source-only draft)

The anonymous `status-github` client introduced in PR #254 already limits
each GitHub response to 512 KiB and each request to 15 seconds. Reading
up to 16 scoped committed tasks can otherwise involve many requests,
so per-response limits do not prevent a prolonged session or a large
aggregate transfer.

This hardening adds **per-client, shared session budgets**:

- At most **52 GET attempts** (including failed HTTP/transport requests).
  This covers one pinned commit and tree, plus up to 16 task/result
  reconciliations with at most three GETs each.
- At most **8 MiB of received response bodies** across the client.
- At most **120 seconds** from the first valid GET. Each request timeout
  is also capped by the remaining session time, and a response arriving
  at or after the deadline is refused rather than returned as successful.

A lock serializes requests sharing one adapter instance so concurrent
callers cannot evade these budgets. Bad paths and write-capable methods
are denied before consuming any budget or performing network I/O.

Exhaustion is **fail-closed**: `ValueError` is handled by the existing
redacted CLI refusal path. No partial history is returned, no results
are interpreted as permission to retry or dispatch, and no raw logs are
printed. An operator may initiate a new, explicitly opted-in read
session, but there is no automatic retry.

Fixtures cover request count, cumulative bytes, deadline before a GET
and after a read, shortened per-request timeout, and denial of
mutation methods before network I/O. Exact-head Mac verification and
independent review remain required. No installed daemon, Chat Bridge,
Chrome, Codex, GitHub Actions, or `main` changes are introduced.
