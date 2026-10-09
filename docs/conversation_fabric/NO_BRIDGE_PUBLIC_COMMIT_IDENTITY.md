# No-Bridge pinned commit identity and strict anonymous GitHub JSON (draft)

This source-only hardening stacks after the anonymous public evidence reader
in PR #254. It does not introduce a new transport, credential, Git writer,
ChatGPT Send/ACK or Local Agent task execution mode.

## Threat addressed

An injected or inconsistent GitHub Commit API response could previously
provide a valid-looking tree SHA without a matching top-level commit SHA.
An attacker-controlled JSON decoder response could also silently accept
duplicate object keys or the non-standard Python NaN/Infinity constants.
A branch/routing mismatch should not be converted into a credible task
history observation.

## Fail-closed checks

- Both the single-task evidence reader and scoped history index now require
  the GitHub Commit API's top-level sha to equal the operator's complete,
  independently pinned agent-control commit. A missing or different identity
  aborts **before** any further file/tree read.
- The anonymous public API reader rejects duplicate JSON keys at every
  nested object level and non-finite JSON constants. Any such error blocks
  the read without returning a partially accepted observation.
- Existing independently pinned tree and per-file Git blob SHA checks remain
  mandatory, along with source commit SHA, canonical agent binding,
  exact work branch and task/result digest reconciliation.
- No success, task dispatch, automatic retry, browser effect or source
  authentication is inferred merely from the ability to read a Git commit.

Negative tests simulate absent/changed commit identities and duplicate
top-level/nested keys, NaN and Infinity. Actual GitHub Commit API responses
include a top-level sha; the isolated existing fake APIs are updated to
represent that actual schema.

No GitHub Actions, Codex, Chat Bridge, daemon restart, global setting or
main branch change. Full exact-head Mac suite and independent security/
integration review are still acceptance gates.
