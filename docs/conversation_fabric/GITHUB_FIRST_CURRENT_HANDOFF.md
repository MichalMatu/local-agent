# GitHub-first Conversation Fabric — current Milestone 8 handoff

> **M8 global admission follow-up (2026-10-09; separate draft branch).**
> The follow-up source-only audit is on
> `work/m8-global-admission-audit-20261009`; its design and explicit
> external-exclusion blocker are in
> [GLOBAL_TRANSPORT_ADMISSION_AND_RETIREMENT.md](GLOBAL_TRANSPORT_ADMISSION_AND_RETIREMENT.md).
> The new audit is **not loaded into the running Bridge**, provides no
> browser-effect permit, and does not establish old/offline legacy retirement.
> At recheck, `main=76865cbc7d92861998e8e33a96193d95c120fe02`;
> #209, #214, #239 and docs-only #240 remain OPEN DRAFT and unmerged.
> Independent PR reviews for #209/#214/#239 were empty. Local Agent
> `agent-control/.agent/status/daemon.json` reported idle, binding
> `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`, at
> `2026-10-09T08:16:14Z` (snapshot only). The first audit head
> `f5c72ce0` passed exact-head Mac task
> `local-agent-m8-global-admission-audit-mac-20261009-v2` (Bridge Node
> suite, Node 26.3.0, Python 3.13.9, exit 0). A prior test syntax error
> in v1 was corrected. The *later* evidence-continuity and browser-effect
> inventory changes require their **own exact-head** verification.
> Independent reviews, cross-device tests and global legacy exclusion remain
> unverified. Do not activate GitHub-first Send/ACK, modify global Bridge
> Master, merge these PRs or restart the daemon based on this document.


**Updated: 2026-10-09. Canonical continuation entrypoint for this track.**
All source SHAs and PR states below are **observations at handoff**, not locks;
re-read GitHub before code edits, task publication or merge.

## Latest current checkpoint — 2026-10-09

This checkpoint supersedes the historical SHA snapshots and old mandatory
six-job hosted-CI wording below. GitHub Actions are disabled for automatic
runs and must not be dispatched. Validate candidate heads via canonical Mac
Local Agent or an isolated sandbox under `LOCAL_VERIFICATION.md`.

At this snapshot, `main` is `f84129a37c102310d74d7176f9156f90b603c39d`
(merged #233 local test gate, #234 strict JSON type parity, #235 strict parent
tree root reader, #236 HTTP no-redirect for token-bearing public GitHub REST).
Draft #209 is `cc7fcd80e111b54dc2574c92ba07d3b4dacb0d43`, and stacked
draft #214 is `9d1d2d3adb8d8a145d870260297966911d3324f7`.
Every SHA is only a recorded observation: recheck GitHub live heads.

The latest #214 exact-head focused Mac task
`local-agent-m8-private-tree-atomic-proof-20261009-v1` passed 57/57 Python
tests, reader/no-Send guard JS, compile and Ruff. Full Mac coverage/native
and exact-head Chromium tasks were separately queued; do not count them as
PASS unless their terminal result can be inspected. #209/#214 still lack
independent security/integration approval and real shared browser-side
parent admission, including legacy/offline worker exclusion. Both remain
**draft and unmerged**. No private `parents/` record, actual GitHub-first
Send, ACK or result was published. Current production remains legacy DOM.

## Current operator override — 2026-10-09: no GitHub Actions

**Binding development rule:** hosted runner credits are exhausted until the
operator chooses otherwise. `main@09d646fbd6a701801c6eda56ea148f259d4adaf9`
changed `.github/workflows/ci.yml` to **manual `workflow_dispatch` only**:
no `push` or `pull_request` activation. The workflow is retained for possible
future explicit operator activation, but **do not dispatch it**. Pending
historical workflow runs and older handoff references to mandatory six-job
CI are not current acceptance gates and must not be treated as successful.

Use the **exact commit SHA** and the Mac's canonical `local-agent` binding
(or an isolated local sandbox) for `scripts/verify.py` and relevant Host Ops,
coverage, macOS/Chromium checks. Persist full command status and bounded
output on the `agent-control` result. See `LOCAL_VERIFICATION.md` for the
current gate. Skip only with an explicit unverified marker; never invent a
successful Mac/browser/Python-3.14 result. Missing independent security and
integration reviews still block #209 and #214 merges. Live GitHub-first
private Send/ACK remains disabled and the legacy DOM mode remains active.

The sections below retain historical source observations for audit only.
Superseded handoff PR #231 and CI-concurrency PR #232 were closed unmerged.
Always re-read the current heads and preserve the manual-only workflow.

## Historical audit snapshot — after PR #226 (superseded)

This section records a **read-only audit**, not live browser/Mac acceptance and
not permission to publish an executable task. All refs must be re-read before
further code changes.

- **PR #226 merged**, squash `b67ad098edb0a7a1acd2d3fed32a77480c99ddd0`, after the exact-head
  `377f7ce89ed1623759e0cb9aa69081ffd8f72f41` workflow completed
  all six required CI jobs successfully. It preserves the current ordinary
  Superchat/legacy DOM flow and adds a manual-only next-window prompt.
- Private `fabric-data` remained at
  `b834209d99f088e093d503632717ae0aaeafbf7f` with no `parents/`
  tree entries on the inspected snapshot. No new private synthetic parent
  record, real Send, ACK, or result was published by this review.
- The observed `agent-control` status at branch
  `c5c4f9603a87064c26cfb41d66dabf31dee4f575` was `idle`,
  self-revision `186ad66480d884670e7043edd7fca340dca2eb9f`,
  binding `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`; that was an
  observation **before** the #226 merge and is not proof of current Mac health.
  The corresponding `.agent/binding.json` and the `local-agent` entry of
  `chat_bridge/runtime.json` matched this binding at inspection.
- **Catalog inconsistency for separate investigation:** the current
  `chat-bridge-state` runtime catalog still lists the frozen donor
  `MichalMatu/host-ops` with `execution_enabled=true`, contrary to the
  canonical execution boundary in `AGENTS.md`. Do not execute or route
  tasks there. Resolve the actual authoritative runtime registry and
  migration status before touching catalog flags or changing bindings.
- Draft #209 remained source-only and fixture-limited on head
  `bf867e5d433cfdb0ebefccd0ec3ba8bf9c6e1e20`; stacked draft #214
  remained at `9e64517bdb4f5f1ddce20ef0e1758a9f3dd5af22`.
  Both exact-head workflow runs completed successfully, but the two earlier
  delegated **independent** security/integration review responses were not
  evidenced in PR reviews/threads. Do not invent them, re-delegate blindly,
  or merge either draft based on CI alone.
- **Historical #214 review gap, fixed in later drafts:** the earlier Python CAS origin reader checked
  parent-tree paths but does not verify Contents decoded blob bytes against
  the tree entry SHA. The separate JS private parent reader performs that
  check. Later draft #214 source and negative tests now verify exact path,
  metadata and decoded Git blob SHA-1; live mode admission is still absent.
  Recorded in [#214 review comment](https://github.com/MichalMatu/local-agent/pull/214#issuecomment-6073474628).
  The current old DOM path is not globally fenced by this synthetic preview.
- #195 remains a deferred successor roadmap PR, and #227 is a separate
  open draft concerning operator launch recovery. Do not conflate their
  readiness with Milestone 8 GitHub-first production acceptance.

## 1. Goal and authority

Product target: a Superchat on desktop/phone can explicitly rehydrate an
authorized project/workflow after the original ChatGPT tab is closed.
GitHub-backed records are authoritative coordination/evidence; ChatGPT is
the reasoning/UI layer; Local Agent is the only deterministic machine executor;
Chat Bridge is a browser effects/observation driver. Child chats reason only.

A Chat Bridge `[LA_CHAT=...]` label is **transport/scheduling only**, not a
repository execution binding. Resolve the **current** conversation's own
`conversation_controls` record; never reuse a predecessor chat ID or its
scheduling generation as authority in a resumed or cross-device session.
Executable Local Agent tasks MUST be published only to the canonical target repository with the exact
`chat_bridge/runtime.json` catalog `agent_binding` after checking
`execution_enabled`, the `agent-control` daemon record, and an exact source
head. Never issue tasks for an execution-disabled repository.

Never change the global Bridge Master through conversation desired state.
Conversation-specific scheduling/pacing changes require this chat's exact
`conversation_controls` record and incremented `control_generation`.
Do not use legacy LAB add/rebind/schedule markers for ordinary Superchat flow.

**Operator decision (2026-10-09):** Keep using the current ordinary ChatGPT
Superchat and working legacy DOM delegation for this development session.
Defer automatic child-to-successor-Superchat promotion until the GitHub-first
private transport, durable workflow/ACK/results and cross-device admission are
actually complete. Prepare **manual** new-window handoff only from a stable
GitHub checkpoint; use GITHUB_FIRST_NEXT_SUPERCHAT_PROMPT.md, not automatic
children that gain independent authority.

## 2. Revalidated source and remote state (2026-10-09)

| Surface | Handoff observation |
| --- | --- |
| Public code repo | `MichalMatu/local-agent`, `main@b67ad098edb0a7a1acd2d3fed32a77480c99ddd0` |
| Private data repo | `MichalMatu/local-agent-fabric-private`, `fabric-data@b834209d99f088e093d503632717ae0aaeafbf7f` |
| Local Agent | `agent-control` daemon `idle` at recheck; observed self revision `a1ba2be840098a727e9de06323ae8625955a6e1e` (may lag latest `main`; re-check) |
| Canonical executable catalog entry | `local-agent` / `MichalMatu/local-agent`, execution enabled, binding `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`; **re-check, do not hard-code** |
| GitHub-first production flag | `github_fabric_read_only_intake_enabled` absent from remote runtime; treated as disabled |
| PR #209 | **OPEN / DRAFT**, head `bf867e5d433cfdb0ebefccd0ec3ba8bf9c6e1e20`; 6/6 checks green on exact head, not yet merged |
| PR #195 | **OPEN** older independent Superchat-to-Superchat roadmap documentation; head `9d88b5554527687439e23b6703307e262b0362f7`, base differs from current `main`; inspect before any merge, do not treat as delivered cross-chat continuity |
| PR #210 | **MERGED**, authenticated GET-only private synthetic recovery smoke |
| PR #211 | **MERGED**, pinned index-only private multi-project catalog reader |
| PR #212 | **MERGED**, authenticated GET-only private project catalog CLI smoke |
| PR #213 | **MERGED**, canonical GitHub-first handoff (squash `8aacbac7673206c98ad866f1425e03f5796b932c`) |
| PR #215 | **MERGED**, predecessor-chat-independent handoff control rule (squash `a1ba2be840098a727e9de06323ae8625955a6e1e`) |
| PR #214 | **OPEN / DRAFT**, stacked on PR #209; synthetic-only trusted private global parent CAS, head `9e64517bdb4f5f1ddce20ef0e1758a9f3dd5af22`; six exact-head CI checks and Mac focused tests passed; not merged |
| PR #216 | **MERGED**, default-disabled unimported source-pinned private global parent reader, squash `11c3fa49c86ae2849f0ceaa68aa968f8a5cdb3ef`; exact-head six CI checks and Mac Bridge suite passed |
| PR #217 | **MERGED**, previous handoff reconciliation, squash `98486c7e339dc39c503802182a097c93857992fc` |
| PR #218 | **MERGED**, verify private parent record/index decoded bytes against pinned Git blob SHA, squash `845d25888820e7f585c5e3fa2e31de382d6d01c2` |
| PR #219 | **MERGED**, authenticated Mac GET-only twice-read private parent namespace absence smoke, squash `3004a75b38b4621b5417cf26c04c539ef421c842` |
| PR #220 | **MERGED**, production Bridge private-import and GitHub-first no-Send regression test; Mac and exact-head six CI checks passed; squash `2654e9a04e4bec7eadc36c5d99c5a82e04239d67` |
| PR #221 | **MERGED**, private parent reader five-second headers/body abort deadline; exact-head Mac Bridge suite and all six CI checks passed; squash `a5d92bdb3ffa0367c5d3cea125f61c0ccc594d46` |
| PR #222 | **MERGED**, latest prior canonical handoff checkpoint; squash `40c854d5112028aecf8dfcfad17b0130e8f005e1` |
| PR #223 | **MERGED**, unconfirmed legacy DOM terminal feedback now appears as `assumed` in operator snapshot and inspect rather than falsely `delivered`; exact-head Mac + six CI passed; squash `8bbd46f29ef1aa2a562660c1fd627c98d533df03` |
| PR #224 | **CLOSED / SUPERSEDED** by #225 due conflicts after #223 merged; not merged |
| PR #225 | **MERGED**, unknown terminal feedback no-prune and bounded fail-closed retention, exact-head Mac and six CI checks passed; squash `186ad66480d884670e7043edd7fca340dca2eb9f` |

Two reasoning-only child reviews were delegated in an earlier Chat Bridge
parent conversation: `m8-parent-fence-verification` (security/correctness)
and `m8-parent-fence-integration` (DOM/GitHub integration seams). Their
actual final responses were **not present in this handoff context**.
Before deciding on PR #209, inspect existing Bridge feedback/campaign state;
do **not** invent reviews or repeat a pending delegation. If feedback is
partial, document precisely which independent coverage is missing.

Do not merge PR #209 based on CI alone; confirm safety/integration feedback,
inspect its latest diff, and verify mergeability against current `main`.

## 3. What is proved versus what is not

**Proved with real GitHub/Local Agent evidence (synthetic only):**

- A fixed, known-public *synthetic* dispatch was published to the private
  `fabric-data` branch, record first, dispatch index second, workflow index
  last. The trusted writer converged and an identical rerun was `replay`
  with zero further writes.
- Private source `b834209d99f088e093d503632717ae0aaeafbf7f` contains
  `projects/local-agent/workflows/workflow-001` with dispatch ID
  `fabric-696175f5b3b215d1c434e87c61bda8de` and two synthetic children.
- The fixed synthetic record equals the approved public reference record.
- A read-only GitHub recovery was performed twice using the Mac's existing
  authenticated `gh api` GET session and returned the same SHA and two
  children, both `published_execution_unconfirmed` with no actual ACK.
- PR #210 supplies a repeatable, explicitly enabled
  `python -m local_agent.conversation.github_fabric_private_live_smoke
  --verify-private-synthetic-read` command; #212 adds the project catalog
  live read smoke. They do **not** grant browser Send rights.
- PR #214 has an unmerged atomic parent record+index CAS implementation on a
  stacked draft branch; deterministic fake GitHub race/replay/corruption
  tests and exact-head Mac checks passed. This is *not* real private fence
  publication or production exclusion.
- PR #216 added a production-unimported, default-disabled authenticated
  reader of an immutable private parent index and all records; fake network
  tests, exact-head Mac Bridge suite and six GitHub CI checks passed. The
  reader always returns `browser_effects_permitted=false`.
- A real authenticated GET-only Local Agent smoke in PR #219 read the private
  `fabric-data` branch **twice** at exact SHA
  `b834209d99f088e093d503632717ae0aaeafbf7f` and reported
  `no_parent_records_observed`, `ack_state=not_attested`,
  `browser_effects_permitted=false`. The separate production-unimported
  private parent reader in PR #218 now verifies decoded JSON bytes against
  their commit-pinned Git blob SHA, not only API metadata.
- A further exact-main Local Agent GET-only regression at
  `main@2654e9a04e4bec7eadc36c5d99c5a82e04239d67` performed
  3 successful private reconstructions (each twice): two synthetic children
  remain `published_execution_unconfirmed`, the `growclip`, `local-agent`
  and `shelly-link` catalog remains indexed as expected, and the global
  `parents/` namespace remains absent. No browser ACK or Send happened.
- Existing DOM-based child delegation in normal Chrome has separate
  previously accepted 1/1 and 3/3 campaign evidence in
  `CHECKPOINT_2026-10-08_BRIDGE_0813_LIVE_ACCEPTANCE.md`.

**Not yet proved/implemented for production:**

- Private real-user bootstrap publication and a secure, revocable
  Chrome-extension reader credential lifecycle; no credential in content
  scripts, ChatGPT DOM, public config or logs.
- One globally enforced **parent-scoped** transport-mode/epoch fence honored
  by both old DOM and future GitHub-first browser drivers before any
  tab/composer/Send side effect. PR #209 is **preview only**, not authority.
- Genuine browser-originated read/submit ACK, durable registered child
  identity, verified terminal result writeback, unknown-submission handling
  and safe retirement/epoch handoff.
- End-to-end cross-device/new-chat project rehydration, offline/restarted
  Chrome behavior and original-tab/old-extension safety.

Never describe synthetic claim/dispatch/result projections as real ACK,
consumer execution or proof that a child completed. Missing evidence stays
`unconfirmed` / `requires_reconciliation`, never automatically retried.

## 4. Private repository data layout

```text
fabric-data:
projects/index.json
projects/growclip/workflows/index.json                 # []
projects/shelly-link/workflows/index.json              # []
projects/local-agent/workflows/index.json              # ["workflow-001"]
projects/local-agent/workflows/workflow-001/dispatches/index.json
projects/local-agent/workflows/workflow-001/dispatches/fabric-696175f5b3b215d1c434e87c61bda8de.json
```

The **project/workflow folders are organizational, not access boundaries**.
A repository Contents:read token can normally read every project. Global
parent mode exclusion must be keyed by canonical parent conversation
identity **across projects**, not separately within each project directory.
PR #209's current branch documents proposed global `parents/` identity,
not the old project-scoped draft. No new live workflow/claim/result records
have been authorized in this private repository.

## 5. Code map

| Responsibility | Canonical code / documentation |
| --- | --- |
| Operator and child identities | `local_agent/conversation/operator_contract.py`, `contract.py`, `bootstrap.py`, `spawn.py` |
| Private synthetic publishing | `github_fabric_private_publication.py`, `github_fabric_private_github.py`, `PRIVATE_SYNTHETIC_PUBLICATION.md` |
| Private dispatch cold recovery | `github_fabric_private_recovery.py`, `github_fabric_private_live_smoke.py`, `PRIVATE_SYNTHETIC_RECOVERY.md` |
| Project/workflow index-only discovery | `github_fabric_private_catalog.py`, `PRIVATE_GITHUB_READ_TRANSPORT.md` |
| Parent exclusion *preview* | PR #209 `github_fabric_parent_fence_preview.py`, `PARENT_TRANSPORT_FENCE_PREVIEW.md` |
| Parent synthetic private CAS | PR #214 `github_fabric_parent_fence_private_github.py`, `PARENT_TRANSPORT_FENCE_PRIVATE_CAS.md` (**draft**, not merged) |
| Unimported private parent reader | `chat_bridge/github_fabric_private_parent_fence_reader.js`, `PARENT_TRANSPORT_FENCE_PRIVATE_READER.md` (**merged**, always no Send authority; Git blob digest verified since #218) |
| Private parent namespace absence CLI | `github_fabric_private_live_smoke.py --verify-private-parent-namespace-empty`, `PRIVATE_PARENT_NAMESPACE_LIVE_SMOKE.md` (real Mac GET-only smoke, #219) |
| Production activation regression | `chat_bridge/github_fabric_private_activation_guard.test.js` (**merged** in PR #220; detects accidental private imports or Send from public intake) |
| Private reader request deadline | `chat_bridge/github_fabric_private_parent_fence_reader.js` (**merged** PR #221; aborted GET including streaming body) |
| Legacy browser Send/claim and results | `chat_bridge/worker_conversation_fabric.js`, `worker_spawn*.js`, `spawn_result_content.js` |
| Inactive browser GitHub intake | `chat_bridge/worker_github_fabric_intake.js`, `github_fabric_private_transport.js` |
| Target product rules | `TARGET_PRODUCT_ARCHITECTURE.md`; repository-wide invariants `AGENTS.md` |
| Existing DOM behavior | `CURRENT_PLAN.md`; separate live restart test `NEXT_CHAT_PROMPT.md`; `assumed` feedback operator status (#223) and durable no-prune retention (#225), both merged |
| Manual new-window continuation | `GITHUB_FIRST_NEXT_SUPERCHAT_PROMPT.md`; **not** automatic Superchat succession |

## 6. Safe next work, in order

1. Obtain/inspect the two already-delegated reasoning-only review results,
   or record missing feedback without duplicate automatic delegation.
   Re-review **latest** PR #209 source, tests, global parent ID, conflicts
   and the distinction between simulated fencing and live enforcement.
2. If reviews warrant it, make the smallest PR #209 corrections, run exact
   head focused tests via canonical Local Agent and applicable exact-head Mac/sandbox gates; merge
   only after passing review and GitHub mergeability. Otherwise leave draft
   and explain blocker.
3. Review the separate PR #214 implementation for synthetic-only private CAS.
   It has atomic parent record+index commits, pinned complete-tree reads,
   race tests and strict zero-write replay. **Do not merge the stacked draft**
   before PR #209's outstanding review gate is resolved, then revalidate
   its base and exact-head local Mac/sandbox gates. No real private parent publication occurred.
4. The browser reader is already merged in PR #216, but it is unimported
   and always denies side-effect authority. Next design/implement **both**
   transport consumers agreeing
   on one authoritative mode/epoch before any side effect. An old/offline
   Chrome version that does not honor fencing is a migration blocker; a
   timeout or missing ACK never grants a takeover.
5. PRs #220 and #221 are merged after exact-head Mac and six required CI
   checks. The additional authenticated three-surface private read completed
   successfully (`local-agent-m8-main-private-three-surface-read-20261009-v1`)
   on its pinned earlier main SHA; do not mislabel it as evidence for later
   commits. No production Send/ACK or private parent write was attempted.
6. PR #225 is merged after exact-head Mac and six CI gates. Its predecessor
   #224 was closed without merge after a conflict with #223. Never prune an
   unconfirmed terminal notification as though its delivery were proved;
   preserve no-replay semantics, and fail closed on history capacity saturation.
7. Implement real evidence-bearing ACK/results, retirement and cross-device
   recovery in bounded gated PRs. Leave all new production flags disabled
   until real acceptance, not merely fixture CI.
8. Postpone any automatic Superchat successor/promotion feature. The next
   ChatGPT window is a user-chosen manual handoff from the durable checkpoint,
   using GITHUB_FIRST_NEXT_SUPERCHAT_PROMPT.md. A new chat must resolve its
   own managed conversation controls and canonical repository binding.

Use connected GitHub tooling for exact-source edits and PRs. Use Local Agent
only for authorized Mac commands, tests, browser/device effects. Confirm
target repo from runtime catalog and exact `agent_binding` at **each** task.
For code PR acceptance, require exact-head `test`, `coverage`,
`python-314`, `absorbed-host-ops`, `bridge-browser`, `macos-smoke`.
If a check is pending/cancelled/failed, do not call it passing or silently
merge. Do not change Bridge Master or any production GitHub-first setting.

## 7. One clear document entrypoint

Read `AGENTS.md`, this file, `TARGET_PRODUCT_ARCHITECTURE.md`,
`CURRENT_PLAN.md`, then inspect fresh GitHub refs/PRs #209 and #214 and the concrete
source files for the next task. The earlier
`GITHUB_FIRST_IMPLEMENTATION_HANDOFF.md` describes the *pre-publisher*
2026-10-08 snapshot and is historical, not current instructions. The older
Stage 8 `HANDOFF_PROMPT.md` is explicitly archival.
`NEXT_CHAT_PROMPT.md` addresses a **different** legacy Chrome-reload
acceptance exercise and should not be used as the GitHub-first kickoff.
For an operator-approved manual new ChatGPT window, copy the prompt from
`GITHUB_FIRST_NEXT_SUPERCHAT_PROMPT.md` after the current development checkpoint
is stable. It confers no runtime handoff authority.

This handoff is documentation of observed facts, not a standing authorization
to spawn child chats, publish real prompts or execute machine commands.
