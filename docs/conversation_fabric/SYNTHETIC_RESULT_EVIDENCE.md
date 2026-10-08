# Synthetic GitHub Fabric terminal-result evidence preview

Status: **default-disabled, strictly synthetic and not an ACK**.

This slice makes the `operator_result` contract discoverable alongside
the known-public synthetic dispatch and semantic-node claims. The result
projection has an immutable SHA-256 digest and bounded per-child digests,
request/node/transaction links and a derived result ID. It deliberately
omits raw child bootstrap text and summary content.

The synthetic fixture simulates completion of two children. **Those children
did not actually execute.** The published projection therefore retains
`kind=public_synthetic_unattested_terminal_fixture`,
`ack_state=not_attested` and `execution_state=not_attested`; clients must
not render it as genuine completed child work or a consumer ACK.

## Causal publication

A trusted Local Agent writer first verifies the exact, existing public
fixture allowlist. No caller-supplied `synthetic` bit authorizes a write.
It then reconstructs both the indexed dispatch and indexed semantic claims
from one commit-pinned GitHub origin. Only a matching predecessor revision
can acquire a fast-forward-only ref update.

The synthetic result record and its bounded index are written together
in one Git tree commit. Identical replay makes no commit. Same-ID changed
content, orphaned records, dangling index references, unknown paths,
denied reads, malformed GitHub state and exhausted CAS retries fail closed.
After timeout or lost GitHub ACK the writer re-reads the exact source before
deciding whether any mutation remains.

The result writer neither imports into Chrome nor changes Bridge runtime,
polling, scheduling or production tabs. A read-only observer never obtains
permission to click Send from these synthetic records.

## Required gates for actual completion evidence

1. Real user bootstrap/terminal contents stay outside the public
   `chat-bridge-state` repository. Provision a private GitHub data repo
   with restricted, revocable writer/reader credentials.
2. Before any browser side effect, a single authoritative Local Agent
   parent-mode fencing claim must exclude legacy DOM/GitHub double execution.
3. Implement a genuine browser-originated receipt/ACK path to the trusted
   GitHub writer. A synthetic or locally invented ACK must never be accepted.
4. Verify terminal child evidence against child registration, original
   transaction, local spool and matching authoritative GitHub operator
   request/result. Only then can a real terminal status be published.
5. Rehydrate results through source-pinned private project view; report
   stale/offline/unknown evidence rather than inventing completion.

This PR is a durability/causality test slice, not full live E2E.
