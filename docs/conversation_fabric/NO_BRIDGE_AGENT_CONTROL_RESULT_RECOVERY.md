# No-Bridge agent-control result recovery (draft)

This source-only reader is independent of Chat Bridge. It lets a new
conversation review the deterministic machine executor's existing, GitHub-
stored task/result evidence without using a browser extension, sending
new prompts, or triggering another execution.

## Inputs and checks

Function: local_agent.conversation.github_fabric_agent_control_recovery.
recover_agent_control_result()

The trusted caller supplies the complete, independently verified GitHub
agent-control commit SHA, source/tested checkout SHA, canonical Local Agent
binding, work branch and immutable task ID. All arguments are checked before
I/O and the reader is default-disabled.

On explicit enable it performs only three GET requests on the same pinned
Git origin: commit metadata, task JSON and result JSON. Both files have strict
size limits, checked GitHub Contents metadata and recomputed Git blob SHA-1.
Task/result association is checked by a canonical SHA-256 of the complete
task JSON, compared to the Local Agent result's task_digest.

Only tasks **declaring** allow_write=false with resources=[] and the
source-head shell guard can yield a review summary. This metadata and
lexical guard do not sandbox a shell or independently verify command effects. The reader requires the
work branch, binding, command texts and task result digest to agree. It
projects reported success only for a done task, all reported zero exit
codes, passed stages, and no timeout, leak, truncation, write or dirty checkout.
A terminal report with all required success indicators but a truncated
command output is classified as reported_incomplete_evidence_for_review,
not reported_nonpass_for_review and not an authenticated PASS. A real
failed/inconsistent/uncertain run remains reported_nonpass_for_review. All
outcomes are review-only and never automatically retried. Malformed, missing, altered or oversized data fails
closed.

## Authority and privacy boundaries

- Return object excludes raw command output, error logs, environment,
  GitHub token, raw task contents, private input and shell command strings.
- Both reported_pass_for_review and reported_nonpass_for_review are
  **GitHub artifact observations**, not independently authenticated proof
  of Mac command execution.
- No call from this source reader can create/delete/modify tasks or Git refs,
  authorize Send/ACK, claim child results, restart the daemon, or retire
  old/offline Chrome workers.
- A pinned SHA supplied by the same untrusted party as the records does
  **not** prove source provenance. Verify GitHub origin and task binding
  out of band before relying on the summary.
- A recorded exact-head shell guard is a lexical review gate; a result record
  cannot cryptographically attest that a shell actually executed it. Only
  the trusted Mac Local Agent runtime and separate operator review provide
  that level of assurance.
- This is a bounded read-only evidence component. It does not complete
  the missing live ChatGPT transport or the required global legacy-effect
  exclusion.

## Verification

Unit tests use an isolated deterministic GitHub API fake that supplies
proper base64 Git blobs and matching SHA-1; cover tampered blobs, mismatched
task digests and command texts, all deny-before-I/O inputs, an aborted or
uncertain run, and read-only projections. Exact-head Mac and independent
review gates remain mandatory for acceptance.

This PR is stacked on the synthetic PR #244 (itself stacked on #243).
Keep all draft; main and the running daemon remain unchanged.
