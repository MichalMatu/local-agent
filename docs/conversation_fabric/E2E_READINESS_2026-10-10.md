# Conversation Fabric E2E readiness — 2026-10-10

> **Historical pre-live checklist, superseded for the private MVP.**
> The authenticated Chrome private GitHub-first one-child E2E PASSED later on
> 2026-10-10 with Bridge 0.8.18 (private claim/ACK/result verified).
> Use [the current handoff](GITHUB_FIRST_CURRENT_HANDOFF.md) and
> [updated MVP runbook](GITHUB_FIRST_MVP_TRIAL.md) for active work.
> The remainder of this document preserves pre-trial gate evidence, not
> current readiness or production-wide authorization.

This is the current **operator-facing test gate**, not an automatic activation
of the future private GitHub-first browser transport. Historical 0.8.13
screenshots and PR/SHA snapshots remain audit evidence only.

## Current verified boundaries

- Source: `main@9041a2a55c708cb78c390ca366b79320401bea9c` before
  this readiness change; re-read GitHub HEAD before running any test.
- `chat_bridge/manifest.json` declares Chat Bridge **0.8.14**.
  This is the **repository manifest version**, not independent proof of the
  version installed in the operator's Chrome profile.
- PRs **#227** (durable operator-launch no-replay fence), **#242** (terminal
  assistant-message scope) and integration **#272** were merged. Both
  original PRs are closed as merged, not outstanding development work.
- On 2026-10-10 the combined source passed canonical Mac task
  `local-agent-final-integrated-full-mac-20261010-v1` on integration
  SHA `f7d47a182c22aac0959d400c6494aabf95a70237`
  (`done`, exit 0). Full local matrix included Python compile/lint/tests,
  Bridge Node tests, macOS smoke, Host Ops design/architecture/coverage
  and **83.1% core branch coverage**. This is **not** a live Chrome E2E.
- The daemon self-updated once and returned idle at
  `9041a2a55c708cb78c390ca366b79320401bea9c`.
  No extension install/reload was performed in that operation.
- Normal DOM `LOCAL_AGENT_CF` delegation is the current working path.
  Source-only private GitHub-first transport and global parent-fence
  preview remain **unimported / disabled**; there is no production private
  Send, browser ACK, global epoch admission or automatic successor-chat flow.

## Gate A — exact-head source verification, no production browser

On a **separate clean checkout of the candidate branch**, not the daemon's
installed checkout, run with the canonical bound Local Agent. Check the SHA,
working-tree cleanliness, current binding and enabled runtime catalog entry
before submitting any task. The test runner must not update installed
extensions, modify production browser profiles or start a second operator
Chrome. An **isolated temporary Playwright Chromium profile** is allowed for
fixtures; it is not the user's Chrome session.

1. Run `node chat_bridge/conversation_fabric_control_diagnostics.test.js` and
   `node chat_bridge/github_fabric_private_activation_guard.test.js`.
2. Run `node scripts/conversation_fabric_dom_smoke.cjs`. It must admit an
   exact terminal assistant control even when turn-level UI text follows it,
   ignore later toolbar mutation without double-delegation, reject actual
   trailing assistant prose, and leave the parent composer untouched.
3. Run `node scripts/conversation_fabric_browser_smoke.cjs`. This exercises
   the **offline installed MV3 extension** on simulated pages, including
   multiple children, delayed/ambiguous identity, service-worker interruption,
   durable capture, cleanup and at-most-once feedback.
4. Run `node scripts/github_fabric_readonly_browser_smoke.cjs`. This is
   an **offline, read-only** GitHub fixture proving the intake does not
   spawn browser work and preserves its ledger across Chromium restart.
5. Run `python scripts/verify_local.py --expected-sha "$(git rev-parse HEAD)"
   --profile full --include-browser --sanitize-test-lease-markers` if local
   prerequisites are installed. This adds the full repository gate and
   isolated Chromium profiles. Pass `LOCAL_AGENT_PLAYWRIGHT_MODULE` only
   if needed for an installed, isolated Playwright package. Do not globally
   install dependencies into the production daemon environment.

**Record actual results** with task ID, candidate SHA, exit code, specific
browser tests executed and any unavailable prerequisites. Historical PASS on
a different SHA is not a PASS on this branch.

## Gate B — preflight in the existing authenticated operator Chrome

This gate has **not been evidenced** by the source-only tests. The operator
must independently check, in the **existing** Chrome profile:

- Installed extension version is the intended build (repository manifest
  alone cannot establish that); content scripts loaded in the existing tab
  are from the same build. Do not silently install/reload a different build.
- The intended **exact parent conversation URL** is registered and enabled,
  Chat Bridge Master is enabled and the parent has the correct active tab.
- The popup/campaign inspector shows no live campaign, uncertain prior
  feedback, conflicting child ownership or blocked full-history retention.
  Preserve ambiguous receipts; never clear local storage to obtain PASS.
- The user approves any extension/service-worker reload during a live
  campaign. Do not use a second Chrome instance, CDP on the user profile,
  copied cookies, Native Messaging or unauthorized GitHub private tokens.

If any item cannot be checked, **stop as UNVERIFIED**, not PASS.

## Gate C — first *live legacy DOM* E2E, operator supervised

With Gate A passed and Gate B checked:

1. Have one managed parent issue one valid **terminal, plain-text**
   `LOCAL_AGENT_CF` delegate containing **two bounded reasoning-only
   children**. Each child gets a different ID. Do **not** publish machine
   tasks or private GitHub-first dispatches through the children.
2. Confirm exactly one admitted campaign and exactly one bootstrap Send per
   exact owned child. Keep both child tabs open.
3. Observe stable result capture and two valid completion footers. Record
   child IDs, owned URLs, campaign ID, capture/Result Vault status and any
   failure reason; do not infer completion from an idle DOM.
4. Recover results through normal campaign polling and confirm exact owned
   tab cleanup and **one** terminal parent feedback. A claimed/assumed
   feedback send is not proof the parent received it.
5. Confirm no repeated child bootstrap and no repeated terminal feedback
   after normal polling. Report PASS/PARTIAL/FAIL with timestamps and
   anonymized, bounded evidence. Do not automatically repeat a failure.
6. **Separate optional interruption acceptance:** only with fresh explicit
   operator supervision, reload the MV3 worker/extension once **during an
   active new campaign**, keep the child tabs open, and prove exact-claim
   recovery without replay. This is not covered by an offline smoke PASS.

Rollback means **stop creating new campaigns**, preserve durable
claims/results and uncertain receipts, and inspect. Never delete a fence,
reset storage, resend an ambiguous bootstrap or reinstall the extension to
force a PASS.

## Gate D — future GitHub-first *private* production E2E (NOT READY)

The offline GitHub fixture does not grant production browser effects. Before
a **real private GitHub-first Send/ACK** can be exercised:

1. Design and independently review a revocable extension-only read credential
   lifecycle, separate trusted writer authority and bounded secret handling.
2. Create one durable **global parent-scoped mode/epoch admission fence**,
   enforced by both **legacy/offline** DOM drivers and GitHub-first drivers
   before any tab/composer/Send effect. Handle revocation and stale workers.
3. Finish an approved private publisher and exact immutable CAS/record
   authority with real, verified browser-origin ACK, result publication and
   unknown-submission/no-replay reconciliation.
4. Prove cold Chrome restart, cross-device and successor-chat rehydration,
   negative races and operator-controlled rollback. Obtain independent
   security/integration acceptance before enabling the feature.

PRs #209/#214 and related experiments were closed **unmerged and archived**
on 2026-10-10. Do not re-open them or misrepresent their synthetic proof as
production readiness. The currently installed DOM Bridge remains authoritative
until the separately approved transport migration is complete.

## Reference paths

- `docs/conversation_fabric/CURRENT_PLAN.md` — legacy DOM control contract.
- `docs/conversation_fabric/GITHUB_FIRST_CURRENT_HANDOFF.md` — M8 target,
  historical private experiments and the current override.
- `docs/conversation_fabric/LOCAL_VERIFICATION.md` — exact-head Mac gate.
- `docs/conversation_fabric/NEXT_CHAT_PROMPT.md` — historical live reload
  procedure (not automatic authorization).
- `agent-control/.agent/results/` — durable Local Agent test evidence.
