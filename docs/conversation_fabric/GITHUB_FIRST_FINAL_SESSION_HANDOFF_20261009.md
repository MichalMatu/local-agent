# GitHub-first Conversation Fabric M8 — final handoff for a new chat

**Snapshot date:** 2026-10-09 (read-only verification after the final Mac
tasks; exact observations, not permanent locks).
**Authoritative live state remains GitHub, not this document.**
This document is maintained on the documentation-only handoff branch
`work/m8-handoff-final-20261009`; it has not been merged to production
`main` to avoid triggering a Local Agent self-update/restart.

## Operator decisions (non-negotiable until explicitly changed)

1. **Never consume Codex credits or start Codex agents/tasks/reviews.** Use
   direct connected GitHub operations for source/reviews and the already
   installed canonical Local Agent on Mac for local command/test work.
2. **GitHub Actions hosted execution is disabled** because credits ran out.
   `.github/workflows/ci.yml` has manual `workflow_dispatch` only.
   Do not dispatch it, re-enable `push`/`pull_request`, or interpret
   absent hosted checks as PASS. On inspection: **0 queued, 0 running**.
3. Keep the current ordinary ChatGPT Superchat and **working legacy DOM
   Chat Bridge delegation**. Do not alter global Bridge Master, existing
   production scheduling or restart the Mac daemon as part of a handoff.
4. **GitHub-first private Send/ACK remains OFF.** Do not publish real
   `parents/` records or real private child prompts, grant browser effects
   from synthetic records, or use a local Chrome marker as global admission.
5. Postpone automatic Superchat-to-Superchat succession until GitHub-first
   and cross-device continuity are production ready. Handoff is manual.
6. **For the closing chat: read/update docs and inspect existing results
   only; do not start another task, local test, GitHub workflow or Codex job.**
   A future chat may resume explicit source work after fresh checks.

## GitHub source and runtime checkpoint

| Surface | Verified state |
| --- | --- |
| Code repo | `MichalMatu/local-agent` |
| `main` | `76865cbc7d92861998e8e33a96193d95c120fe02` |
| PR #209 (synthetic parent preview) | OPEN **DRAFT**, head `556d03bfc18e8276e1e61ed7cb5997c1a8666d58`, base `main@76865cbc`; 3 own files; 0 behind; mergeable |
| PR #214 (private parent Git CAS) | OPEN **DRAFT**, head `d834a8473b82054dd84e63b806a2da7ff2b18e86`, base #209 at `556d03bf`; 5 own files; 0 behind; mergeable |
| PR #239 (local legacy DOM suspension seam) | OPEN **DRAFT**, head `7ffddf1e66d418c8ce8eccaa0ef744a6bad5da16`, base `main@76865cbc`; 6 own files; 0 behind; mergeable |
| Other open PRs | #227 (operator-launch reliability, unrelated draft); #195 (deferred successor roadmap, **not** the production solution) |
| Private data | `MichalMatu/local-agent-fabric-private`, `fabric-data@b834209d99f088e093d503632717ae0aaeafbf7f`; verified recursive tree contains **no `parents/` entries** |
| Local Agent daemon | `idle`, `current_task_id=null`; self revision `76865cbc7d92861998e8e33a96193d95c120fe02`; status updated `2026-10-09T08:00:55.248127+00:00` |
| Canonical binding | `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`, equal across daemon, `agent-control/.agent/binding.json`, and `chat-bridge-state/chat_bridge/runtime.json`; `local-agent.execution_enabled=true` |
| Hosted Actions | `ci.yml` is manual-only; 0 queued/0 running at handoff |

**Runtime catalog warning, do not act blindly:** `chat-bridge-state`
still advertises the frozen donor `MichalMatu/host-ops` as
`execution_enabled=true` (binding
`16d688b6-b0ef-4905-a5bd-24e59c99cfb4`), contradicting
`AGENTS.md` which forbids executable donor tasks. Do not publish tasks
there. Check authoritative registry, ownership and migration status in the
new chat before requesting an approved catalog-only correction; **do not
alter the binding or restart anything during this handoff**.

## Final Mac results — all finished, exact candidate SHAs

All three task result artifacts were read from `agent-control/.agent/results/`
and have `status=done`, command exit `0`, and clean Git status.

| Candidate | Durable task result file | Verified evidence |
| --- | --- | --- |
| #209 `556d03bf` | `local-agent-m8-restacked-preview-mac-20261009-v1.json` | 25 Python tests PASS; private JS parent reader and no-Send guard PASS; Ruff PASS |
| #214 `d834a847` | `local-agent-m8-restacked-cas-mac-20261009-v1.json` | 58 Python tests, private JS reader/no-Send, Ruff, compile PASS (earlier focused task) |
| #214 `d834a847` | `local-agent-m8-restacked-cas-full-local-20261009-v1.json` | **991 Python tests** PASS; full `scripts/verify_local.py --profile full` Mac test matrix (including Host Ops, native/macOS checks, lint, coverage) PASS; core coverage **83.4%** versus 70% gate |
| #239 `37c761aa` (superseded head) | `local-agent-m8-pr239-legacy-latch-node-20261009-v1.json` | Bridge Node tests and Ruff PASS; superseded by later browser-test commit |
| #239 `7ffddf1e` | `local-agent-m8-pr239-latch-browser-20261009-v2.json` | **Entire Bridge Node suite + cached Chromium 1228/Playwright 1.61.1 browser suite PASS**, including 4-child delegation, MV3 restart, no replay, synthetic suspension marker preventing new tab creation |

Read the actual JSON outputs to establish any claims beyond these summaries.
No hosted Actions or Codex were used for these gates.
**Mac Python 3.14 compatibility must not be assumed** unless a separate
exact-head interpreter run is evidenced. A passing isolated MV3 smoke is not
a real cross-device old-extension retirement proof.

## Exact source changes and intentional non-changes

- #209: immutable global parent identity and epoch-1 **synthetic** mode
  preview; `browser_send_authorized=false`; cannot grant live authority.
- #214: bounded private GitHub parent index+record tree CAS; commit-pinned
  Contents/blob/tree integrity, no redirect, exact SHA + literal `force:false`,
  fixed allowed Git tree paths and atomic parent/index pair; no real
  `fabric-data` parent write. Code remains draft pending review.
- #239: `worker_legacy_dom_effect_gate.js` local **deny-only** marker
  `conversationFabricLegacyDomEffectSuspension`. A missing key preserves
  existing DOM behavior; any present value or storage error fails closed
  at child tab creation, content preparation and spawn messaging. It is
  introduced before `worker_spawn.js` by `service_worker.js`. Synthetic
  browser smoke sets the marker only in a disposable test profile.
- #239 is **not an authoritative global transport fence**. Older Chrome
  versions/offline workers ignore the marker, the local read-to-effect
  interval is not atomic, and parent feedback/cleanup seams still require
  comprehensive audit. Do not merge/ship or set it in production yet.
- No actual GitHub-first private browser Send, trusted terminal ACK, real
  two-device mode admission, old-worker retirement, or automatic Superchat
  successor has been demonstrated.
- No source branch was merged in this handoff session; all three PRs are
  intentionally drafts. There is **no need to restack them again** absent
  new `main` commits or an observed conflict.

## Independent review and acceptance blockers

- GitHub PR reviews for **#209, #214 and #239 are empty** at snapshot.
  Earlier delegated reasoning-child security/integration reviews were not
  recoverably evidenced; do not invent or duplicate them blindly.
- Design a **global, authoritative parent-scoped transport admission and
  retirement protocol**, including previously installed/offline legacy
  workers. No valid local marker or expiring lease by itself can establish
  exclusion or permit GitHub-first Send.
- Prove no child tab creation, content submission, result reuse or terminal
  feedback can double-apply across restart, ambiguous ACK, two browsers or
  disconnected/rejoining devices. Treat unknown effects as suspended;
  never auto-replay them.
- Add trusted real browser Send/ACK/result publication only **after** the
  global old/new transport ownership and review gates are proven.
- Carry out controlled real-device / real-Chrome acceptance with the
  operator explicitly involved, a fail-closed rollback and monitoring plan;
  isolated Chromium is useful regression evidence, not that acceptance.

## Suggested order for a *new* chat

1. Read `AGENTS.md`, this handoff, `TARGET_PRODUCT_ARCHITECTURE.md`,
   `LOCAL_VERIFICATION.md`, root `README.md` and
   `CURRENT_PLAN.md`; recheck live `main`, `fabric-data`, exact
   PR heads and daemon/catalog bindings. Check outstanding reviews before
   touching source.
2. Review #239's five source/test/doc boundaries (6 files) specifically
   for **legacy DOM compatibility**, races, missing feedback/cleanup
   effect sites, and offline version exclusion. Keep it draft.
3. Propose and review a separate **global admission + retirement** design
   before activating browser code. Favor an explicit fail-closed state
   machine and epoch-bound proof over a local toggle, stale-read expiry,
   or another independent scheduler.
4. Only with necessary review and user-authorized scope: continue small
   GitHub PR edits and run **exact SHA** Mac/sandbox tests through the
   canonical Local Agent. Never use Codex or GitHub Actions quota.
5. Do not start Superchat succession automatically; produce a new
   manual handoff if the user changes chats again.

## Operational handoff

- This is a **documentation-only checkpoint**. Do not merge its PR into
  `main` during the closing chat: an installed daemon may self-update from
  `main`; the operator requested **no further launches or restarts**.
- Read the docs-only PR branch explicitly when beginning the next chat;
  the historical `main` handoff starts with older SHA observations.
- Continue using the current legacy DOM Bridge. Chat identity is
  scheduling/transport metadata, **not execution authority**. Every real
  executable Local Agent task must use exact current repository binding and
  source SHA. Do not execute tasks for donor/disabled repositories.
