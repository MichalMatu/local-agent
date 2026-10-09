# No-Bridge command/stage correlation in reported Mac receipts

Status: source-only DRAFT, stacked after the no-Bridge handoff in #256.

## Review finding

A result can report a successful overall stage and a zero-exit command yet
carry a conflicting or missing command-level stage identifier. Checking
those observations separately is not enough to classify a coherent PASS.

The narrow `AgentControlReadOnlyObservation` validator now requires the
corresponding reported command **and** stage to carry the same:

- `stage_phase="commands"`
- strictly integral `stage_index` equal to the expected 1-based index
- strictly integral `stage_total` equal to the number of task commands
- `stage_name="command-<index>"`

It still verifies command text identity, source-head guard, work branch,
binding, digest, zero exit, success outcome, clean Git status/diff and all
no-timeout/no-resource-leak signals. Missing, contradictory or booleans-as-
integers stage fields downgrade a coherent `done` status to
`reported_nonpass_for_review`, **never** an attested PASS.

The reported outcome is permanently review-only; `automatic_retry_permitted`,
`effect_authorized`, `result_execution_attested` and cross-parent browser
authorization remain false. A record is a GitHub report, not signed proof of
actual Mac execution. An otherwise consistent success with a truncated log
continues to be `reported_incomplete_evidence_for_review`.

Tests cover wrong stage name, missing name, bool/wrong index and total,
incorrect phase, and the history projection. Test fixtures model the
real Local Agent command metadata observed in task/result JSON.

No Chat Bridge, Codex, GitHub Actions, browser Send/ACK, daemon restart,
`main` modification or PR merge. Exact-head canonical Mac tests and
independent security/integration review remain required.
