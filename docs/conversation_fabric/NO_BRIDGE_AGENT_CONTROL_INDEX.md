# Commit-pinned no-Bridge task-history discovery (draft)

This continuation stacks on PR #245's strictly read-only, redacted
single-task result reader. It does not depend on a Chat Bridge conversation
ID, Chrome tab, browser session, daemon restart, or GitHub Actions.

## What it provides

discover_agent_control_results() accepts an operator-chosen task ID prefix,
independently pinned agent-control Git commit, source checkout SHA, work
branch and canonical Local Agent binding. It is default-disabled. Once
explicitly enabled, the reader performs GET-only repository calls:

- Read the exact Git commit and its tree SHA.
- Read a bounded, non-truncated recursive tree for that commit.
- Identify up to 16 scoped task/result JSON paths under .agent/tasks and
  .agent/results. Reject unexpected scoped paths, duplicate tree entries,
  unsafe blob modes/types, malformed IDs, orphan result paths and oversized
  source inventories.
- Independently re-read every completed task/result pair through PR #245's
  per-task evidence verifier. The GitHub Contents SHA must also equal the
  SHA of its pinned Git tree entry; the decoded file's blob SHA is checked
  separately by the per-task reader.

The output is a frozen, redacted operator-review object containing
completed, reported-only observations and IDs for task records that have
no result yet. Missing results mean **unconfirmed**, not permission to
requeue. Unrelated tasks outside the explicit prefix are excluded.
No test log contents, command bodies, tokens, or private prompts are included.

## Trust and safety

A GitHub commit is a state snapshot, not a cryptographic attestation of
Mac command execution. The operator is responsible for verifying the
commit SHA and binding independently. The reader does not contact the
browser or ChatGPT; it cannot authorize Send, ACK, terminal outcomes,
an automatic retry, or old/offline legacy-worker retirement. It does
not publish task state or mutate Git refs.

Failures in any selected completed record abort the whole scope, rather
than quietly discarding a problematic result. The bounded tree and exact
file SHA checks detect inconsistent or incomplete GitHub Contents data.

## Verification

Focused in-memory GitHub tests include successful one-task discovery,
an explicitly unconfirmed pending task, malformed and duplicate paths,
truncated trees, dangling results, changed blob SHA, altered task/result
digest and no-I/O disabled or incorrectly pinned inputs.

Keep this PR stacked and draft until exact-head Mac verification and
independent security review. main and installed daemon are unchanged.
