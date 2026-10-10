# GitHub-first Fabric — universal pre-effect fence contract (candidate)

Status: **source-only / default-disabled / NO browser authority**.
This protocol must be reviewed and integrated across **all** legacy DOM and
GitHub-first controllers before any new multi-child Chrome Send test.

## Problem and authority boundaries

A parent ownership record alone cannot guarantee at-most-once browser Send.
A pinned read becomes stale immediately; a local MV3 storage claim is not a
cross-device compare-and-swap (CAS). Chrome can suspend after submission while
the private GitHub ACK/result is absent. Missing evidence is **not** proof of
an unsent prompt.

The shared remote authority is the fixed private GitHub `fabric-data` branch,
with non-force fast-forward Git ref updates. The current candidate implements:

- Parent ownership and immutable epoch witnesses in
  `local_agent/conversation/github_fabric_parent_ownership_github.py`.
- Commit-pinned read-only parent/epoch observation in
  `chat_bridge/github_fabric_private_parent_ownership_reader.js`.
- Immutable deterministic per-child effect IDs, monotonic effect revisions
  and no-replay policy in `github_fabric_effect_intents.py`.
- An opt-in private CAS effect ledger writer and receipt-only reconciliation
  in `github_fabric_effect_intents_github.py`.
- A separate per-child MV3 journal v2, not imported by the installed worker.

**None grants a browser Send permission.** Even `recorded_no_send` means the
intent may have been durably committed, not that a browser is safe to submit.

## Safe progression for one parent epoch

1. **Parent admission:** from indexed immutable private dispatch, atomically
   acquire a unique owner/epoch and immutable witness. Ref conflicts,
   different owners and earlier unknown epochs fail closed.
2. **Child readiness:** verify a managed parent, immutable bootstrap digest,
   the child identity and page-local tab conditions, without Submit. Persist
   local child phase intentions separately.
3. **Global effect intent:** atomically append one deterministic effect ID in
   `projects/local-agent/parent_ownership/effects/<parent-id>.json`.
   It starts at `send_unknown`, since a crash between the commit and Send
   can never establish whether the browser submitted.
4. **One-shot authorization — NOT IMPLEMENTED:** a future universal controller
   must be able to prove the new CAS is its own successful commit, its
   authority has not been revoked, the current epoch still matches and every
   possible Send driver has joined the gate. A read-back after lost ACK,
   ordinary parent snapshot, replay or storage recovery is **not** a permit.
   Auth must not be recoverable/reissued to a resumed worker, even if the
   same process or device claims the same owner ID.
5. **Browser Send — NOT IMPLEMENTED:** only after all gates pass, persist
   page-local `submission_unknown` **before** touching the composer;
   perform at most one actual Submit. No retries after worker teardown,
   timeouts, uncertain DOM responses or missing child ACK.
6. **Receipt-only reconciliation:** verify the independent child claim,
   ACK and terminal result from one pinned private commit; only a completed
   child may change its effect record to `result_verified`. Never infer
   `result_verified` from a child URL, local flag or absence of errors.
7. **Next sibling:** sequential child order is enforced; every previous
   effect must be `result_verified`. Reusing the old child/transaction/effect
   is forbidden forever within the epoch.
8. **Terminal release:** the parent can complete only with complete matching
   evidence for all children. `frozen_unknown` must remain a permanent
   no-takeover fence; no automatic TTL/lease timeout/takeover.

## Candidate CAS ambiguity and collision rules

- A ref update is fast-forward-only; one stale writer loses. A 409/422 or
  transport error causes **one** fresh, pinned read-only reconciliation.
- An identical remote ledger after a lost PATCH can be reported as
  `converged_no_send`; that return value is **not** a license for Send.
- An absent/mismatched record or changed epoch requires reconciliation,
  never blind CAS retry and never Send. An unreadable ref becomes
  `EffectIntentOutcomeUncertain`.
- New effect entries use immutable child request ID, spawn transaction,
  parent epoch, dispatch and owner; all must match the indexed dispatch.
- The candidate ledger is bounded to four ordered child effects; storage
  corruption, duplicated effects, forged verified result, owner drift or
  missing receipt is refused.

## Explicit integration blockers

**Legacy DOM path:** it currently does not possess the new private dispatch
identity or obtain a shared parent epoch. The existing local fence in
`worker_github_fabric_private_live.js` only protects one extension instance.
Do not activate a remote gate for GitHub-first alone while legacy Send paths
remain unjoined; that would create false confidence.

**MV3/cold restart:** the worker must never reissue a one-shot permit or Send.
The candidate journal and the parent reader are both unimported. A private
read token kept only in session storage is not an automatic recovery channel.

**Candidate reader integration:** the independent, default-disabled
`chat_bridge/github_fabric_private_parent_effects.js` validates the
effect-ledger schema, deterministic per-child effect IDs, sequential
verified-child admission, monotonic revision and unknown/frozen phases.
`github_fabric_private_parent_ownership_reader.js` now recognizes effect
paths in the SAME pinned Git commit/tree, checks Git blob SHA over decoded
bytes and validates each selected parent ledger against the current owner
and epoch. It rejects orphan/duplicate/missing-root effect paths, tampered
records and absent child identity evidence. All projected states explicitly
have `browser_effects_permitted: false`.

**Still blocked:** the JS reader receives `expectedChildren` as an explicit
argument; it cannot independently prove that the caller obtained these
child IDs and spawn transactions from the SAME pinned indexed dispatch.
The universal driver must authenticate that dispatch at the identical Git
HEAD, not merge evidence from a moving ref or from browser inputs. A
completed old-epoch effect ledger remains a mismatch after a subsequent
parent-epoch takeover; an explicit immutable historical effect-ledger
lifecycle and migration rule must be reviewed instead of silently
overwriting the old record. Neither issue is Send-authorized.

**Cross-device testing:** require deterministic two-controller ref collision,
lost acknowledgment both before/after the ref update, stale old epoch,
competing legacy/GitHub-first paths, worker teardown after each phase, and
independent review of TOCTOU gaps.

**Real Chrome:** separate operator approval is required before any installed
extension reload or live two-child Send. The historical claim-only live
dispatch remains unresolved and must not be replayed.

## Evidence and safe continuation

The pure and CAS modules have focused isolated tests:
`tests/test_github_fabric_effect_intents.py` and
`tests/test_github_fabric_effect_intents_github.py`. Mac acceptance must use
exact repository `agent_binding` and checked HEAD. These tests establish
offline data-contract invariants only; they do not imply a live or global
browser fence.
