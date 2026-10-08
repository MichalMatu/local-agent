# GitHub Fabric — synthetic cold recovery proof

Status: **default-disabled, read-only, approved public fixture only**.

This slice introduces `local_agent/conversation/github_fabric_recovery.py`.
It reconstructs a bounded, commit-pinned observation snapshot from the same
GitHub origin as the existing synthetic dispatch and atomic semantic claims.

Read algorithm:

1. Verify the exact known-public fixture fingerprint before opening GitHub.
2. Resolve the trusted `chat-bridge-state` head once; read every file by
   that precise commit SHA, never mixing mutable branch-head responses.
3. Confirm the indexed immutable dispatch equals the approved fixture.
4. Confirm the claim index names all expected semantic workflow nodes.
5. Validate **every indexed** claim, including unrelated entries, and
   reconcile expected digests, parent, node and transaction identities.
6. Return a bounded source SHA, workflow/parent, dispatch and child-node view.
   All child lifecycles explicitly remain
   `published_execution_unconfirmed`.

No browser storage, captured DOM, child transcript, local campaign or original
ChatGPT session is required to rebuild this *synthetic observation snapshot*.
Missing dispatches, claims, invalid indexes, mutated identities, 403 or
incomplete GitHub state fail closed. Restart and repeated reads issue no Git
mutation and never imply permission to resubmit a browser prompt.

**Not an ACK or terminal result:** an immutable claim or Bridge's local
`seen` fingerprint is not proof that an authorized child saw the work,
clicked Send or returned a terminal result. The snapshot intentionally has
no ACK, result, child URL or send-authorized fields. The production browser
worker does not import or call this reader.

**Not private transport:** the current public repository and
`chat-bridge-state` surface cannot host real private bootstrap text or
raw terminal evidence. A separately authorized, private GitHub data repo
and authenticated, revocable read path must be accepted before lifting the
fixed synthetic allowlist.

Later acceptance requires a GitHub-backed parent ownership/fencing claim
shared with old DOM delegation; protected child prompts; genuine consumer
read ACK; trusted terminal-result verification and writeback; and one
origin-pinned cross-device project view with last-sync/staleness information.
None of those prerequisites is bypassed by this read-only proof.
