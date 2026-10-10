# GitHub-first Conversation Fabric — current handoff

**Checkpoint: 2026-10-10. One real private GitHub-first child E2E: PASS.**
This is the active continuation entrypoint for PR #274. The longer historical
Milestone 8 timeline is preserved in Git history; it is not a second runbook.
Re-read all refs before writing code, submitting tasks or deciding to merge.

## Source of truth at handoff

| Surface | Verified state |
| --- | --- |
| Public repository | `MichalMatu/local-agent` |
| Production `main` | `f9f73e97a061d5ba590021ddae14b45f705cb7ae`, **not modified** |
| Candidate | `work/fabric-github-first-live-mvp`; re-read PR HEAD; last full source gate `fcd7d260a3decbef9d64c2e5a2ad339800e2fe17` |
| Pull request | [#274](https://github.com/MichalMatu/local-agent/pull/274), OPEN/DRAFT, targets `main`, **not merged** |
| Control branches | `agent-control`, `chat-bridge-state`, `operator-control` — operational, not disposable |
| Private transport | `MichalMatu/local-agent-fabric-private:fabric-data` |
| Local Agent | `4.20.6`, idle at last read, canonical `agent_binding=2180d453-1357-4fbc-be1a-e1e5b8fbb10a` |
| Candidate Chat Bridge | `0.8.18`, content protocol `26`; installed in operator's existing authenticated Chrome |
| Operator Chrome | Same existing profile; no second Chrome instance or profile |

**Important:** The candidate HEAD may advance through further documentation
edits. The SHA above describes the independently checked functional checkpoint,
not a checkout pin for future work. The installed extension is not automatically
updated when source code changes; distinguish source, staged files and actual
reloaded browser code.

## What was actually accepted

The **second**, operator-launched single-child private GitHub-first trial
completed in the existing Chrome profile:

- Parent: `https://chatgpt.com/c/6aca323f-ec58-83eb-bb3f-5be611bc7770`.
- Private dispatch: `fabric-a8a79801818a745c63c9e3674597522e`.
- Child request: `fabric-live-verify-02`.
- Child: `https://chatgpt.com/c/6aca5422-3a90-83ed-b2e1-3baaf114533f`.
- Browser assistant reply: `FABRIC_PRIVATE_E2E_V2_OK | value=42 | role=verification`,
  followed by the exact ASCII completion marker.
- **Independently verified on private GitHub:** the immutable `claim`, browser
  `ack` and terminal `result` files exist under
  `projects/local-agent/workflows/workflow-001/receipts/<dispatch-id>/`.
  All three carry the same child ID and transaction; ACK and result agree on the
  exact child URL; result includes the expected answer and assistant identity.
  The private result stores answer text without the footer (intentional).

The first dispatch
`fabric-13795c4be8cc6d08c8cda3120d6efebd` **did not pass**:
its private `claim` exists, but ACK/result are absent. The original page
reported no local page-level Send claim, no composer and no user messages,
but that is not authoritative proof that browser Send never occurred. Its
`submission_unknown` state is preserved; **never retry that dispatch** or
erase the claim to make a test pass.

This checkpoint proves one-child **private GitHub-first
claim → browser Send → ACK → stable terminal result**. It does **not** prove
multi-child parent aggregation, cold Chrome/MV3 restart recovery, global
cross-device exclusion, automatic successor Superchat, or merging safety.

## Implemented and tested in the candidate

- Indexed, validated private OperatorRequest/ChildRequest ingestion through the
  canonical Mac Local Agent, immutable private dispatch publication and
  pinned private reads.
- Browser worker: operator-only launch, GitHub-managed exact parent admission,
  unique private claim, existing authenticated Chrome UI driver,
  durable unknown-Send fence, private ACK/result and no automatic Send replay.
- Popup: separate persistent dispatch-ID save, **session-only** scoped token,
  masked four-character suffix, remembered Advanced settings, explicit status.
  Token never belongs in public GitHub, page DOM, task logs or documentation.
- `0.8.17`: pre-submit fresh-page/composer readiness gate: when ChatGPT loads
  slowly, stay in `tab_ready` and retry readiness only; never silently
  re-arm a recorded ambiguous Send.
- `0.8.18`: operator-only abandon action can fence a genuine
  `submission_unknown` trial without resending and excludes that dispatch
  ID from future launches. The existing successful second trial is not
  abandonable. A **later candidate-only popup fix** disables the button
  outside `submission_unknown` and preserves actual status on rejection;
  do not assume this later JS is already loaded in Chrome.

Evidence on `agent-control`: `local-agent-fabric-abandon-0818-final-gates-20261010-v2`
passed the full Bridge suite; `local-agent-fabric-popup-phase-guard-20261010-v2`
passed the final popup/worker checks. Earlier isolated Chromium tests also
passed, but those are separate from the real Chrome trial. PR #274 includes
live-evidence comments. GitHub Actions are manual-only due to operator cost
constraints; **do not dispatch Actions without approval**.

## Non-negotiable continuation rules

1. Read `AGENTS.md`, this handoff, `GITHUB_FIRST_MVP_TRIAL.md`,
   `TARGET_PRODUCT_ARCHITECTURE.md` and the candidate PR diff/tests.
2. Re-read live `main`, candidate HEAD, open PRs, private `fabric-data`
   and `.agent/status/daemon.json` on `agent-control`.
3. Work only on `work/fabric-github-first-live-mvp` until the operator
   chooses otherwise. Never touch or merge `main` as housekeeping.
4. All **executable** work goes through a fresh exact source-head Local Agent
   `.agent/tasks` job with the actual target's **canonical agent binding**.
   GitHub code edits may be made directly on the candidate branch.
5. Do not restart Local Agent or Chrome, reload the extension, resend an
   uncertain bootstrap, close owned child tabs, clear storage, or change the
   global Master state without specific operator approval.
6. Keep private prompts, GitHub tokens and unredacted child records in the
   private repository. Public tasks/results/PR comments carry opaque IDs and
   bounded non-sensitive evidence only.

## Continuation checkpoint — 2026-10-10, multi-child read-only milestone

This increment is **source-only**. It does not arm a two-child browser launch,
reload Chat Bridge, change any driver, or alter the accepted single-child live
transaction. Exact tested source HEAD:
`f5f1cda366e9e7ef923b6c594ec029ed45bcf84f`; documentation-only commits also advance branch HEAD; run an exact-head test
gate after the final documentation update before promotion.

### PASS — independently observed or executed

- Existing 0.8.18 **one-child** live private claim/ACK/result remains the
  previously accepted proof; it was **not repeated**.
- New `github_fabric_receipt_aggregation.py`: deterministic projection for
  1..4 children with independently validated claim, ACK and result, strict
  IDs/transaction/digest/parent/URL checks, order-independent input, duplicate
  physical child-URL rejection and no raw prompt/assistant text in outputs.
- `github_fabric_private_summary.py` now reads the dispatch index and every
  child receipt at **one pinned private commit**. It is explicit opt-in,
  read-only, bounds its records and returns only redacted child states. No
  live private summary was executed at this checkpoint.
- The incomplete `claim_only_unknown` state is deliberately not treated
  as an unsent or failed browser action. Invalid/missing predecessor evidence
  requires reconciliation; completed siblings retain their own PASS.
- Mac Local Agent command task
  `local-agent-fabric-multi-receipts-gate-20261010-v1` at source
  `4cae8ead1d6ba98f57fd532740cb9d4a82986710`:
  7 new receipt tests + 12 existing dispatch tests + 2 focused Node
  suites + Ruff, all exit 0, clean checkout.
- Mac Local Agent command task
  `local-agent-fabric-multi-summary-gates-20261010-v1` at exact source
  `f5f1cda366e9e7ef923b6c594ec029ed45bcf84f`:
  7 receipt tests + 4 pinned summary tests + 9 private publisher tests,
  focused worker Node suite + Ruff, all exit 0, clean checkout.
- Both commands were read-only source tests via
  `agent-control` with the freshly confirmed canonical binding. No
  Chrome/extension or Local Agent restart command was dispatched.

### FAIL / unresolved

- The historic first private dispatch
  `fabric-13795c4be8cc6d08c8cda3120d6efebd` remains **NOT PASS**:
  claim exists without ACK/result; browser Send outcome is not known.
  Do not replay, delete, or upgrade that result to a success.
- A synthetic invalid ACK/result, wrong transaction or duplicate child URL
  correctly fails evidence admission by design. This is a negative-test PASS,
  **not** a report of a new real-browser failure.

### UNVERIFIED / blocked gates

- Multi-child browser dispatch, independent browser ACKs/results and actual
  parent synthesis/aggregation consumption in a Superchat.
- Durable per-child MV3 work journal, interrupted/restarted worker recovery,
  cold-browser token restoration and cross-device driver competition.
- Global parent ownership epoch/lease and fencing shared by **all** legacy
  and GitHub-first drivers. A per-dispatch claim is insufficient: different
  dispatches for one parent can otherwise race.
- Real authenticated Chrome two-child execution, extension reload, and
  any browser effects require renewed explicit operator approval.
- Full exact-head source acceptance, isolated Chromium, optional runtime
  dependencies and independent security/integration review were not claimed.

### Next bounded implementation sequence

1. Add a durable **per-child** MV3 journal v2 and a deterministic batch
   cursor. Preserve v1 one-child state untouched during migration. Persist
   individual unknown-Send fences before each possible Submit; no
   automatic replay, including after worker suspension or lost ACK.
2. Introduce private GitHub **parent ownership / fencing** with explicit
   acquisition and release/revocation. Require that every participating
   driver, including old DOM delegation, consults the same authority before
   a Send. Disallow unsafe automatic lease takeover after ambiguous effects.
3. Add synthetic two-child cases: out-of-order completion, one claim-only,
   one malformed terminal receipt, duplicate claims, lost PUT response,
   pause/resume between every phase, and two controllers targeting one parent.
4. Run exact-head Mac Python/Node and isolated MV3/Chromium gates via
   canonical Local Agent. Keep browser work off by default until global
   ownership and no-replay negative tests pass.
5. Ask the operator **before** touching real Chrome/reloading the installed
   extension. Then test two children under supervision, MV3 restart, and
   competing-controller exclusion as separate acceptance gates.

Do not create a separate feature branch, trigger hosted GitHub Actions,
change `main`, rotate operator settings, or infer that read-only aggregation
constitutes a live multi-child PASS.

## Continuation checkpoint — 2026-10-10, journal v2 and global fencing policy preview

**Scope:** source-only candidate work on PR #274. The installed Chat Bridge
0.8.18 and the real single-child browser trial are unchanged. No active
browser driver imports the new batch module. The parent ownership model has
**no** live GitHub CAS writer and grants **no** Send authority.

### PASS

- Candidate `chat_bridge/github_fabric_private_batch_journal.js` stores
  independently identified children under a separate `chrome.storage.local`
  key `privateFabricBatchJournalV2`, without private prompt text or GitHub
  tokens. Version 1's accepted single-child journal is untouched.
- Durable phase intent comes **before** each potentially ambiguous effect:
  `claim_intent`, `tab_open_intent`, then `submission_unknown` before
  any future Send. On restart, such states require reconciliation, never
  automatic duplicate claims, new tabs or prompt submission.
- The pure model permits only one active child at a time, requires a new
  owner identity for each child, validates immutable transactions/digests
  and forbids a second child while an earlier sibling is uncertain,
  abandoned or blocked. Storage transitions require an expected version,
  one admissible phase advance, and read-back; this is **not** cross-device
  compare-and-swap.
- Candidate `local_agent/conversation/github_fabric_parent_ownership.py`
  defines the deterministic parent ID shared with the existing synthetic
  parent reader, frozen uncertain outcomes, unique ownership and proposed
  monotonically increasing epochs. Competing controllers are refused in
  policy tests. A confirmed finished dispatch cannot be rearmed as a new
  epoch, nor can an epoch reuse the preceding owner identity.
- Exact-bound Mac Local Agent tasks returned **PASS / exit 0**:
  `local-agent-fabric-batch-journal-v2-gate-20261010-v1`
  (source `1d89170640aa497ffbee86bafc524c2939b0681b`),
  `local-agent-fabric-batch-journal-v2-hardened-20261010-v1`
  (source `578ad5efa07725d788924872b03fac4d47d4d3e3`),
  `local-agent-fabric-parent-ownership-policy-gate-20261010-v1`
  (source `ee9f00b2a5ac56fa1760fee772f836c7db00dd42`).
  These ran isolated Node/Python tests and applicable Bridge/Ruff gates.
  The subsequent full source gate
  `local-agent-fabric-multichild-journal-final-gate-20261010-v1` at exact
  `fcd7d260a3decbef9d64c2e5a2ad339800e2fe17` also **PASS / exit 0**
  (Python compile, all `test_github_fabric_*.py`, Ruff and complete Bridge
  Node suite). A final documentation-only commit after that gate must
  receive its own exact-head sanity verification.

### FAIL / unresolved

- Historic private dispatch
  `fabric-13795c4be8cc6d08c8cda3120d6efebd` remains **claim-only,
  unknown Send**. Do not retry it or release ownership on inference.
- Negative tests deliberately reject two owners, malformed journals,
  duplicate owners/tabs/URLs, forged storage transitions and incomplete
  aggregate receipts. These are expected regression outcomes, not new
  real-browser failures.

### UNVERIFIED

- Installed Chrome/MV3 worker does **not** consume journal v2; restart
  protection is proven only in Node storage/worker-recreation simulation.
  No claim of live two-child completion or background recovery.
- The parent fencing policy is a **pure preview**, not an atomic private
  GitHub lease/epoch writer. Existing legacy DOM delegation and all other
  controllers do not yet consult a shared authority, so **global exclusion
  is not achieved**. A GitHub writer must use strict pinned origin + CAS,
  refuse ambiguous ref updates, prohibit unverified lease takeover, and
  check the current epoch immediately before every browser effect.
- A full production merge matrix, isolated MV3 Chromium extension recovery,
  cross-device races, any real two-child Chrome trial and real extension
  reload are still blocked/unverified. GitHub Actions remain unused.

### Safe next sequence

1. Build a private GitHub parent-ownership **writer/reconciler** with a
   single parent record and atomic non-force CAS, conflict and lost-update
   tests, and permanent freezing of unknown outcomes. Keep it disabled.
2. Gate **every** Send-capable path, including legacy DOM delegation, on
   current remote epoch/owner authorization; forbid a local storage claim,
   cached read or mere TTL from granting authority.
3. Wire the per-child journal into a separately operator-gated two-child
   worker; enforce one child Send at a time and post-restart read-only
   reconciliation. Require indexed private dispatch + matching browser
   claim/ACK/result for independent children.
4. Run exact-HEAD Mac and isolated Chromium/MV3 tests; require security
   review for race/TOCTOU and offline-owner cases.
5. **Ask the operator first** for installed extension reload and then a
   supervised real Chrome two-child, MV3 restart and competing-controller
   test. Do not treat independent tests as permission for browser effects.

## Continuation checkpoint — 2026-10-10, candidate private parent CAS and epoch ledger

**Source-only safety increment.** Verified functional source HEAD:
`dc3b924b257aecc41252c680f35eed4ee82506bf`. This document update
will advance HEAD; a final exact-HEAD sanity gate is required. The installed
Bridge 0.8.18 and real Chrome workflow were not touched.

### PASS

- New `local_agent/conversation/github_fabric_parent_ownership_github.py`
  implements an **explicitly opt-in**, trusted Local Agent-side candidate
  writer for the fixed private `fabric-data` repository only.
- Every proposed acquisition resolves its exact dispatch from the indexed,
  commit-pinned private intake. The writer atomically commits a parent
  ownership record, sorted global parent index, per-parent epoch history,
  and an immutable per-epoch witness, using `force=false` Git ref updates.
  No browser authorization is issued, and private prompts/results are never
  included in ownership records or returned status.
- Historical dispatch **and owner** identities cannot be reused across
  later completed epochs, not just the immediately previous epoch. An
  ambiguous or active predecessor cannot be silently replaced. The history
  is bounded (32 epochs); capacity exhaustion fails closed.
- Completion is checked against **all** child claim/ACK/result receipts
  from one pinned private commit. Partial, missing, corrupt or mismatched
  evidence cannot close an epoch. Explicit unknown-outcome freeze is
  irreversible by this candidate API.
- Ref contention (409/422), lost PATCH response and uncertain reconciliation
  never trigger a blind second write; a fresh verified read can acknowledge
  exactly matching state, otherwise the outcome stays conflict/uncertain.
- Canonical Mac Local Agent focused task
  `local-agent-fabric-parent-cas-gate-20261010-v2` on
  `dc3b924b257aecc41252c680f35eed4ee82506bf` returned
  **PASS / exit 0**: nine isolated private Git Data CAS tests, four pure
  ownership-policy tests and Ruff. Full task
  `local-agent-fabric-parent-cas-full-gate-20261010-v1` on the same SHA
  returned **PASS / exit 0**: Python compile, all
  `test_github_fabric_*.py`, Ruff and full Bridge Node suite.

### FAIL / unresolved

- The initial `local-agent-fabric-parent-cas-gate-20261010-v1` failed on
  **three new test expectations**: the fake private API records its delegated
  ref update under the shared Git test endpoint; a reused historical owner
  now returns a stricter denial. The test assertions were corrected, and
  v2 plus full exact-HEAD verification passed. This was not a real-browser
  failure or evidence of an unsafe successful CAS.
- The original real Chrome dispatch
  `fabric-13795c4be8cc6d08c8cda3120d6efebd` is still
  **claim-only / unknown Send**, never replayed.

### UNVERIFIED / release blockers

- The new private writer has **not been invoked against the real private
  GitHub data repository**; tests only used a fully isolated Git Data fake.
- **Global parent exclusivity is not yet achieved.** Existing GitHub-first
  and legacy DOM Send paths have not joined this common parent ownership
  epoch/fence. Candidate parent records confer no Send permission.
- Cross-device CAS races against actual GitHub, revocation/TOCTOU fencing,
  installed MV3 cold restart, multi-child browser Send, durable parent
  synthesis and independent security acceptance remain unverified.
- No Chrome/extension/Local Agent restart, browser Send, private receipt
  replay, GitHub Actions dispatch, production `main` edit or merge
  occurred in this increment.

### Next bounded increment

1. Create a **read-only** private browser ownership verifier that matches
   the trusted CAS record, history and epoch witness at one private Git
   commit, with strict owner/dispatch/parent identity and stale epoch
   rejection. It must not expose prompts, tokens or Send rights.
2. Design a universal pre-effect remote fence for **all** legacy and
   GitHub-first Send paths, including explicit authority revocation, cached
   or offline owner refusal, cross-worker and cross-device races. Require
   focused independent review before enabling.
3. Connect the existing candidate per-child MV3 journal v2 only after that
   gate is fully enforced. Test independent child receipts, partial failure
   and restart/no-replay using an isolated browser harness.
4. Ask the operator before any installed extension reload, real Chrome
   two-child trial, or global competing-controller acceptance.

## Continuation checkpoint — 2026-10-10, pinned owner/epoch reader for Bridge

**Scope:** candidate-only, read-only Node/MV3-compatible module on
`work/fabric-github-first-live-mvp`. No installed service worker import,
feature toggle, popup launch, new browser claim or Send behavior.

### PASS

- Added `chat_bridge/github_fabric_private_parent_ownership_reader.js`,
  intentionally separate from the older, synthetic-only parent transport
  preview reader. It uses the actual private candidate CAS paths under
  `projects/local-agent/parent_ownership/` and fixed `fabric-data`.
- The reader requires explicit enablement, a scoped caller-supplied token
  and canonical parent URL plus exact expected owner, dispatch and epoch.
  It reads one authenticated private ref, resolves its commit/tree and
  checks bounded pinned Contents (including actual Git blob SHA-1 over
  exact UTF-8 bytes) for the selected parent record, epoch history and
  **every** immutable witness in that history. It rejects duplicates,
  orphan paths, incomplete index/record/history, mismatched owner/epoch,
  corrupt witness, truncated trees, symlinks and malformed encodings.
- The result contains only redacted observation metadata: matched active,
  completed, frozen, stale/competing or unregistered. It always returns
  `browser_effects_permitted: false`, never a Send capability, token,
  prompt, child text or mutable lease. A private GitHub snapshot can become
  stale immediately after reading.
- Isolated regression tests cover epochs 1 and 2, current vs previous
  owner/dispatch, completed/frozen epochs, invalid/duplicated history,
  missing or tampered epoch witnesses, corrupt tree/blob, denied access,
  rejection before fetch, and no installed worker import.
- Exact-bound Mac source tasks (without browser effects):
  `local-agent-fabric-parent-ownership-reader-gate-20261010-v1`
  and `local-agent-fabric-parent-ownership-reader-full-20261010-v1`
  at functional HEAD `97eac9e2522f1ed58c8a62585d6a5c7cf7f3cd36`
  both **PASS / exit 0**. Full gate covered Python compile, all
  `test_github_fabric_*.py`, Ruff and the full Bridge Node suite,
  including the accepted live-worker fake UI contract and candidate
  batch journal v2. Final documentation-only HEAD still needs its own
  exact-source sanity gate.

### FAIL / unresolved

- The historical private dispatch
  `fabric-13795c4be8cc6d08c8cda3120d6efebd` remains
  **claim-only, unknown browser Send** and must not be replayed.
- Rejecting tampered and stale ownership in negative tests is intended,
  not a real-browser failure.

### UNVERIFIED / blocked

- The new reader is not loaded into the production extension. The CAS
  writer and reader have not been exercised against real private GitHub
  ownership records, only synthetic/mocked contracts.
- **No global Send exclusivity:** installed legacy DOM and GitHub-first
  driver do not share a live authoritative pre-effect epoch gate. Even
  a matching pinned candidate snapshot provides no atomic Send grant;
  TOCTOU, takeover, offline, two-Chrome and multi-child browser gates
  remain blocked.
- No extension reload, Chrome/Local Agent restart, real browser trial,
  GitHub Actions, private `fabric-data` mutation, `main` edit or merge
  in this increment.

### Next work

1. Independently review the full private CAS + JS reader identity and
   GitHub tree/path integrity boundary. Treat pinned observations as
   evidence only, never action authority.
2. Design a universal globally fenced pre-effect protocol that covers
   *all* Send paths, including old DOM delegation and multiple devices,
   with an explicit pending-effect record and no implicit TTL takeover.
3. Only then wire the private per-child MV3 journal and two-child browser
   executor behind operator admission, with no Send replay after suspend.
4. Perform isolated Chromium/MV3 and offline/race tests; seek separate
   explicit operator consent **before** any real installed Chrome
   extension reload or browser Send.

## Earlier accepted multi-child scope (still not live authorized)

Build and independently test **multi-child GitHub-first dispatch** in small
steps, without changing the currently accepted one-child live path:

1. Audit private schema/dispatch/receipt contracts and propose bounded
   2-child admission, ownership and parent aggregation rules. Preserve the
   ability to test each child independently; avoid global Send/replay races.
2. Implement regression tests for distinct child identities, duplicate claim
   protection, per-child ACK/result, out-of-order completion, partial failure,
   and restarted MV3 worker resumption.
3. Run exact-HEAD Mac Bridge/Python tests and isolated MV3 browser smoke
   through canonical Local Agent. Record pass/fail with durable task IDs.
4. Request a **separate supervised real Chrome acceptance** for two children
   after code gates pass; user must approve any extension reload.
5. Test MV3 restart/interruption and finally cross-device global parent
   exclusivity. Do not infer these from the one-child E2E.

Keep PR #274 draft until the operator approves the next merge gate; no
automatic rollout of GitHub-first across conversations.

## Branch and documentation hygiene

At this checkpoint exactly five public branches existed: `main`,
`agent-control`, `chat-bridge-state`, `operator-control`, and
`work/fabric-github-first-live-mvp`. **None is redundant or deletable now.**
There was exactly one open PR, #274. Avoid inventing cleanup by deleting
operational refs or the source branch of an active draft.

This concise handoff supersedes older checkpoint prose in its *own prior Git
revisions*. Legacy DOM runbooks remain historical/legacy-specific evidence.
For a new ChatGPT window, use
[GITHUB_FIRST_NEXT_SUPERCHAT_PROMPT.md](GITHUB_FIRST_NEXT_SUPERCHAT_PROMPT.md).
