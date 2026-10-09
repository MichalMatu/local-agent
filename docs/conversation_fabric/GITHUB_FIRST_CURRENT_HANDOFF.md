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
scheduling generation as authority in a resumed or cross-device session. Executable Local Agent tasks MUST be published
only to the canonical target repository with the exact
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
| Public code repo | `MichalMatu/local-agent`, `main@26469ee634da02941f8fd10225e5c719013ee32c` |
| Private data repo | `MichalMatu/local-agent-fabric-private`, `fabric-data@b834209d99f088e093d503632717ae0aaeafbf7f` |
| Local Agent | `agent-control` daemon `idle`; self revision matches the above `main`; last heartbeat `2026-10-09T00:33:40.248800+00:00` |
| Canonical executable catalog entry | `local-agent` / `MichalMatu/local-agent`, execution enabled, binding `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`; **re-check, do not hard-code** |
| GitHub-first production flag | `github_fabric_read_only_intake_enabled` absent from remote runtime; treated as disabled |
| PR #209 | **OPEN / DRAFT**, head `bf867e5d433cfdb0ebefccd0ec3ba8bf9c6e1e20`; 6/6 checks green on exact head, not yet merged |
| PR #195 | **OPEN** older independent Superchat-to-Superchat roadmap documentation; head `9d88b5554527687439e23b6703307e262b0362f7`, base differs from current `main`; inspect before any merge, do not treat as delivered cross-chat continuity |
| PR #210 | **MERGED**, authenticated GET-only private synthetic recovery smoke |
| PR #211 | **MERGED**, pinned index-only private multi-project catalog reader |
| PR #212 | **MERGED**, authenticated GET-only private project catalog CLI smoke; latest `main` above |

Two reasoning-only child reviews were delegated in the preceding Chat Bridge
parent conversation: `m8-parent-fence-verification` (security/correctness)
and `m8-parent-fence-integration` (DOM/GitHub integration seams). Their
actual final responses were **not present in this handoff context**.
Before deciding on PR #209, inspect existing Bridge feedback/campaign state;
do **not** invent reviews or repeat a pending delegation. If feedback is
partial, document precisely which independent coverage is missing.

Do not merge PR #209 based on CI alone; confirm safety/integration feedback,
inspect its latest diff, and verify mergeability against current `main`.

## 3. What is proved versus what is not

**Proved with real GitHub/Local Agent evidence:**

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
3. Next independent slice: default-disabled **trusted private CAS writer**
   for synthetic-only global parent preview record plus bounded index,
   atomic in one Git commit. Same source/ID replay must write zero commits.
   Reject stale refs, dangling/orphan records, mode conflicts, forged
   Send/ACK, unknown/private user content and ambiguous write outcomes.
4. Only subsequently design/implement both transport consumers agreeing
   on one authoritative mode/epoch before any side effect. An old/offline
   Chrome version that does not honor fencing is a migration blocker; a
   timeout or missing ACK never grants a takeover.
5. Implement real evidence-bearing ACK/results, retirement and cross-device
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
`CURRENT_PLAN.md`, then inspect fresh GitHub refs/PR #209 and the concrete
source files for the next task. The earlier
`GITHUB_FIRST_IMPLEMENTATION_HANDOFF.md` describes the *pre-publisher*
2026-10-08 snapshot and is historical, not current instructions. The older
Stage 8 `HANDOFF_PROMPT.md` is explicitly archival.
`NEXT_CHAT_PROMPT.md` addresses a **different** legacy Chrome-reload
acceptance exercise and should not be used as the GitHub-first kickoff.

This handoff is documentation of observed facts, not a standing authorization
to spawn child chats, publish real prompts or execute machine commands.
