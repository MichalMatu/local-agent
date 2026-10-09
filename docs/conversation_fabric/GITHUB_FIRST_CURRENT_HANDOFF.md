# GitHub-first Conversation Fabric — current Milestone 8 handoff

**Updated: 2026-10-09. Canonical continuation entrypoint for this track.**
All source SHAs and PR states below are **observations at handoff**, not locks;
re-read GitHub before code edits, task publication or merge.

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

## 2. Revalidated source and remote state (2026-10-09)

| Surface | Handoff observation |
| --- | --- |
| Public code repo | `MichalMatu/local-agent`, `main@2654e9a04e4bec7eadc36c5d99c5a82e04239d67` |
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
| PR #221 | **OPEN / DRAFT**, private parent reader five-second network/body abort deadline, head `f8be80a738d33a04f7ffecbe9c54ae968ee8d82a`; exact-head Mac Bridge suite passed, six GitHub CI checks still pending at handoff check |

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
| Private reader request deadline | PR #221 `chat_bridge/github_fabric_private_parent_fence_reader.js` (**draft**; aborted GET including streaming body) |
| Legacy browser Send/claim and results | `chat_bridge/worker_conversation_fabric.js`, `worker_spawn*.js`, `spawn_result_content.js` |
| Inactive browser GitHub intake | `chat_bridge/worker_github_fabric_intake.js`, `github_fabric_private_transport.js` |
| Target product rules | `TARGET_PRODUCT_ARCHITECTURE.md`; repository-wide invariants `AGENTS.md` |
| Existing DOM behavior | `CURRENT_PLAN.md`; separate live restart test `NEXT_CHAT_PROMPT.md` |

## 6. Safe next work, in order

1. Obtain/inspect the two already-delegated reasoning-only review results,
   or record missing feedback without duplicate automatic delegation.
   Re-review **latest** PR #209 source, tests, global parent ID, conflicts
   and the distinction between simulated fencing and live enforcement.
2. If reviews warrant it, make the smallest PR #209 corrections, run exact
   head focused tests via canonical Local Agent and all six CI jobs; merge
   only after passing review and GitHub mergeability. Otherwise leave draft
   and explain blocker.
3. Review the separate PR #214 implementation for synthetic-only private CAS.
   It has atomic parent record+index commits, pinned complete-tree reads,
   race tests and strict zero-write replay. **Do not merge the stacked draft**
   before PR #209's outstanding review gate is resolved, then revalidate
   its base and six CI checks. No real private parent publication occurred.
4. The browser reader is already merged in PR #216, but it is unimported
   and always denies side-effect authority. Next design/implement **both**
   transport consumers agreeing
   on one authoritative mode/epoch before any side effect. An old/offline
   Chrome version that does not honor fencing is a migration blocker; a
   timeout or missing ACK never grants a takeover.
5. PR #220 is merged. PR #221 Mac test has a verified passed terminal
   result (`local-agent-m8-pr221-private-reader-timeout-20261009-v1`).
   Merge PR #221 only when all six GitHub checks on its exact head are green;
   do not mistake a still-running check for success. The additional
   exact-main private three-surface read task also completed successfully
   (`local-agent-m8-main-private-three-surface-read-20261009-v1`).
6. Implement real evidence-bearing ACK/results, retirement and cross-device
   recovery in bounded gated PRs. Leave all new production flags disabled
   until real acceptance, not merely fixture CI.

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

This handoff is documentation of observed facts, not a standing authorization
to spawn child chats, publish real prompts or execute machine commands.
