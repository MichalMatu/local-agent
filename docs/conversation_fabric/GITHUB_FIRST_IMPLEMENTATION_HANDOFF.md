# GitHub-first Conversation Fabric — implementation reaudit and new-chat handoff

Updated: 2026-10-08. Target: `MichalMatu/local-agent`.
Source examined: `main@78c856d8a6212b28320fa533df9d706b1e96fe70`;
the target architecture and roadmap additions are in **PR #194** on
`work/docs-github-first-fabric-roadmap-20261008`.
**At execution time, re-read latest `main` and PR status**: do not assume
the above SHA is still current or that #194 is merged.

## Product decision — fixed target, not implemented

**ChatGPT is intelligence and the user interface; GitHub-backed records are
durable project coordination and evidence; Local Agent is the deterministic,
admission-controlled executor; Chat Bridge is one browser effect/observation
driver.** A project survives closing ChatGPT and can be explicitly rehydrated
in a different authorized chat on a phone or desktop. The user sees completed,
running, failed, decision-required and unknown/stale items with evidence and
last-sync time. No accepted project state relies on the original DOM being open.

Guarantees cover *acknowledged durable records*, not unsent drafts, hidden
reasoning, unrecorded child transcripts or effects from an offline Mac.
Use small immutable records, an auditable causal journal or equivalent existing
durable store, rebuildable snapshots and separately protected large evidence;
do not assume Git history alone is backup. The **GitHub Actions quota must not
affect runtime state**, but missing CI is not a passing result.

## Existing foundations — no reimplementation

| Already implemented | Exact reuse / current limitation |
| --- | --- |
| Semantic operator requests/results | `local_agent/conversation/operator_contract.py` (v3 request, result v1) |
| Child contracts/bootstrap/transaction | `contract.py`, `bootstrap.py`, `spawn.py` |
| Immutable GitHub dispatch builder and validator | `local_agent/conversation/github_fabric_dispatch.py` and `tests/test_github_fabric_dispatch.py`; **does not publish** |
| Bridge dispatch/identity validation | `chat_bridge/github_fabric_dispatch_model.js` and `github_fabric_intake_model.js` |
| Read-only intake behind optional disabled flag | `chat_bridge/worker_github_fabric_intake.js`, `worker_runtime.js`; **does not spawn or post results** |
| Existing minute poll, conversation ownership and freshness | `worker_github_control.js`, `worker_events.js`; reuse, no second scheduler |
| Browser spawn/observation and stable result/vault | `worker_spawn*.js`, `worker_conversation_fabric.js`, `spawn_result_content.js`; current authority still browser-local |
| Durable local workflow/spawn records | `local_agent/conversation/store.py`, `spawn_store.py`; **inspect before adding event stores** |
| Accepted normal Chrome 0.8.13 evidence | `CHECKPOINT_2026-10-08_BRIDGE_0813_LIVE_ACCEPTANCE.md` (1/1 + 3/3); **active-campaign reload not yet live-proven** |

## Reaudit: actual gaps and risky boundaries

1. **Private-data blocker.** The existing dispatch includes exact
   `bootstrap_text` that can contain private project context, while the
   proposed intake index/records are fetched via public
   `raw.githubusercontent.com`. Never publish real private bootstraps to
   this path. First decide whether a synthetic-only public fixture is enough
   for the initial proof and define the *future* authorized private/encrypted
   reader + evidence publisher. SHA-256 alone does not protect secrecy.
2. **Publisher is missing.** `build_github_fabric_dispatch()` builds the
   correct immutable record, but there is no production publication/index
   admission transaction. Preserve existing GitHub control, local identity,
   repository policy and content-addressed conflict semantics.
3. **No authoritative round trip yet.** Bridge read-only intake fingerprints
   dispatch IDs into `chrome.storage.local`. It does not submit tabs,
   accept a GitHub-owned lifecycle, or write verified result/checkpoint
   evidence to GitHub. Do not mistake that seen ledger for an execution queue.
4. **Authority/duplicate risk.** A migration must arbitrate between GitHub
   dispatch and legacy `LOCAL_AGENT_CF` DOM requests so the same work never
   starts twice. No child gets machine authority. Exact page-local transaction
   phases in `SPAWN_PROTOCOL_V2.md` are currently contract-only/inactive.
5. **Cross-device promise needs a read model.** Source records need
   explicit workflow identity, last confirmed revision, pending decisions,
   stale/offline indicators, bounded evidence references and an exact resumption
   path; inspect current workflow stores before designing new append-only
   files or snapshot formats.
6. **Test availability.** GitHub Actions job status must be verified on
   the exact SHA, not inferred from queue or quota. If Actions is unavailable,
   use authorized local/Local Agent verification and leave the implementation
   PR unmerged until a valid required gate is available.

## One narrow next implementation PR — only after parent synthesis

**Goal:** a deterministic *admission-to-publish preflight* using existing
immutable dispatch contracts and GitHub-backed control conventions, covered
by strict tests, default-disabled, **with no live browser effects**.

- Audit current writer/control patterns and durable operator/workflow stores.
- Implement the smallest missing trusted publishing/preflight component
  (or demonstrate it already exists and instead fill its proven test gap).
  Reuse `build_github_fabric_dispatch()`; validate parent/request/child
  ownership, path-derived dispatch identity, immutable record/index and bounded
  size/capacity. Distinguish identical replay from same-ID/content conflict.
- Use only **synthetic non-sensitive** child text and a test/isolated sink.
  Do not publish real data via the public raw endpoint or enable the remote
  read-only flag in production. No GitHub write token in Chrome.
- Add focused Python/JS regressions for malformed/oversized input,
  stale/conflicting records, partial publication/network failure, retry
  identity, restart/idempotency and permission/privacy fail-closed behavior
  where the existing test harness can prove them.
- Stop at one reviewable PR. No production tab creation, parent composer
  mutation, Local Agent task publication, second poller, new generic registry,
  cross-device implementation, or wholesale refactor of Bridge.
- Verify exact-head focused tests and six canonical CI jobs if available.
  Report unresolved CI quota/blocker explicitly. Do not claim full live
  GitHub-first acceptance from a docs change or a fixture-only unit test.

## Recommended three-child audit (children never execute)

The new parent should delegate three **independent reasoning-only** reviews
via the existing installed Chat Bridge Conversation Fabric, **only after**
checking that the user has a managed/enabled parent and no active/undelivered
campaign. Exact child IDs are new for this campaign, not old smoke IDs.

- **Research:** find actual owner/file for trusted control-plane Git writes
  and request-to-dispatch publication. Return reusable functions and the
  smallest missing seam; no code edits.
- **Verification:** assess public raw bootstrap secrecy, replay/identity,
  conflicting dual DOM/GitHub requests and in-campaign restart gate. Return
  blockers and mandatory negative tests; no code edits.
- **Integration:** map already-existing workflow/event/spawn stores and
  GitHub result paths; propose a minimal synthetic-safe publisher preflight
  with deterministic tests and no new framework; no code edits.

The parent must **wait for real completion feedback**, synthesize any missing
coverage, select one implementation slice, and only then edit source/create
one PR via GitHub. Use Local Agent only for machine-local builds/tests or
device/browser execution; the children have no mutation/execution authority.
Never auto-repeat a failed delegation.

## Start prompt for the new parent chat

> Continue `MichalMatu/local-agent` with the **next bounded implementation
> slice** of GitHub-first Conversation Fabric. The **adopted product goal** is
> persistent Mac -> closed ChatGPT -> phone/new-chat project continuity:
> ChatGPT is the interface, GitHub-backed Local Agent records are authoritative
> memory/evidence, Local Agent alone controls deterministic execution, and
> Chat Bridge performs only exact browser UI effects.
>
> First read fresh `main`, `AGENTS.md`,
> `docs/conversation_fabric/TARGET_PRODUCT_ARCHITECTURE.md`,
> `docs/DEVELOPMENT_PLAN.md`,
> `docs/conversation_fabric/GITHUB_FIRST_IMPLEMENTATION_HANDOFF.md`,
> `docs/conversation_fabric/GITHUB_READ_ONLY_INTAKE.md`,
> `docs/conversation_fabric/CURRENT_PLAN.md` and PR #194 status. If #194
> is not on `main`, read its exact head but **do not start from stale main
> or overwrite another branch**. Check installed Chat Bridge and pending
> campaigns before a test.
>
> Use **three independent reasoning-only Fabric child chats** for publisher
> ownership, security/replay/privacy and existing store/test integration.
> Children inspect and report only; parent coordinates, edits and decides.
> Delegate once using a fresh exact terminal `LOCAL_AGENT_CF` block and
> wait for actual Bridge feedback. If not bound/enabled, do not fake children;
> do the code audit at parent level or ask the operator to activate Bridge.
>
> **Implement only the first missing bounded, default-disabled, synthetic-safe
> publisher/admission-to-index seam or a demonstrated equivalent test gap.**
> Reuse existing operator/child/bootstrap/dispatch and workflow store code.
> Do not recreate these contracts; do not publish private bootstrap text over
> public GitHub raw; do not enable GitHub-first spawning, submit prompts,
> replace the DOM path, introduce a second scheduler or claim live parity.
> Treat the active-campaign reload test as a separate gate before browser
> mutation in production.
>
> Verify focused regressions, open one reviewable PR, and require all
> appropriate exact-head CI. If the reported GitHub Actions quota blocks
> verification, record that fact and leave the PR unmerged; do not invent
> passing results. Finish with the exact file/PR/SHA, test evidence,
> blockers and the one next acceptance step. **Avoid duplicated work and
> avoid producing a second strategy document.**
