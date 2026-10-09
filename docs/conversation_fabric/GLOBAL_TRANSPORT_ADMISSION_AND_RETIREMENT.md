# M8 global parent transport admission and retirement — review design

Status: **draft source-only audit**, no production effect authority. Proposed code:
`chat_bridge/github_fabric_global_admission_audit.js` and its Node tests.
The audit is not loaded by `service_worker.js`, the manifest, content
scripts, or the daemon. It does not read secrets or perform network/Chrome
effects. A report of `blocked` is never a permit for any transport.

## Threat model and the missing global primitive

The owner must be the **canonical parent identity**, not the local browser
profile, child transaction, conversation-controls entry, or repository binding.
A GitHub compare-and-swap orders admitted control changes; it cannot prevent
an older extension from calling `chrome.tabs.create`, setting the composer,
submitting a ChatGPT message, collecting a result or emitting terminal feedback.
An offline browser can wake after every local suspension marker or lease has
expired. Consequently **a GitHub parent record, local flag, acknowledged
inventory, monotonic epoch or expiring lock cannot prove global exclusion**.

The controlling safety property is:

> No two active transports may produce effects for one parent/epoch, including
> an old/offline uncooperative worker, and any unknown prior effect remains
> retained without automatic replay.

This property needs an independently enforceable effect boundary and actual
proof of retirement of the older path. The current ChatGPT DOM/Chrome APIs
are not under Local Agent's global admission gate. Treat this as a missing
product primitive, not as a TODO solvable by a stronger local boolean.

## Proposed admission states (design only)

| State | Authority and behavior |
| --- | --- |
| `legacy_active` | Existing DOM delegation remains the only live path; no GitHub-first browser Send/ACK |
| `drain_requested` | New *cooperating* legacy clients may deny further effects; old/offline clients remain possible |
| `retirement_reconciliation` | Record each known browser/device/version, child tab, bootstrap, prompt Send, result reuse, cleanup and terminal feedback; suspend unknown outcomes |
| `external_exclusion_required` | Require separately verified revocation/isolation that blocks every old capable session **at effect time**, including rejoining clients; never infer this from an inventory |
| `candidate_for_review` | Source CAS, independent security/integration review, live controlled two-device/browser acceptance and operator approval all still required |
| `github_first_active` | **Not implemented or reachable** in this milestone; no code in this PR can enter it |

Each migration attempt must preserve a unique parent ID, a strictly
monotonic generation and immutable source/head proof. Any conflicting
observation, exhausted evidence storage, stale/uncertain receipt or partial
device inventory holds the parent in reconciliation; no TTL-based stealing,
automatic requeue or silent rollback.

An acceptable future global exclusion proof must identify exactly **which
enforcer physically denies legacy effects**, scope the denial to the parent
and epoch, establish that uncooperative old binaries and offline sessions
cannot bypass it after reconnect, bind a durable revocation receipt to a
trusted authority and survive crashes/restarts. A browser-produced
`retirement_receipt` string is only a claim, not that proof. Since there
is no such enforcer today, the checked-in evaluator **always denies**.

## Source-only audit contract

`inspectGlobalTransportAdmission` accepts two bounded, strict snapshots
and an operator attestation flag. It reports mismatched parent IDs, epoch
jumps/replay, stale source-head observations, active/offline/unknown legacy
workers, pending/unknown browser effects and missing operator attestation.
Independently of all supplied values it reports four permanent blockers:
unbounded old worker population, missing atomic cross-device effect
exclusion, unavailable trusted external retirement proof, and missing
independent/live acceptance. It exposes
`browser_effects_permitted=false` and `automatic_retry_permitted=false`
only. Empty inventories and all-`retirement_claimed` devices are **not**
proof of exclusion.

`recoveryForEffect` returns evidence-for-review for claimed terminal effects
and suspended/reconciliation for any other outcome. Neither result permits
automatic retry. Receipt SHAs are syntax checked only: they are not verified
against GitHub or trusted browser execution. Both functions are offline
diagnostics, deliberately not an admission service.

The effect map covers child tab creation, content preparation, prompt Send,
result reuse, terminal feedback and owned-tab cleanup. The PR #239 local
suspension seam checks a subset of these in cooperating drivers only; it
must not be promoted to global fencing. Parent feedback and cleanup remain
separate audit sites.

## Required proof before private GitHub-first live execution

1. Independently audit #209's identity/epoch preview and #214's authenticated
   atomic CAS against unauthorized authors, stale reads, malicious content,
   race conditions and source pinning. Their PRs stay drafts.
2. Independently audit #239 for legacy regressions and *all* browser effect
   paths. Default-absent local storage must retain working DOM delegation.
3. Specify and demonstrate an actual old-worker admission exclusion/revocation
   mechanism that applies to previously installed and disconnected versions.
   Inventory/attestation alone is insufficient.
4. Journal per-effect intents and outcomes with durable non-replay semantics.
   Unknown effects must remain `requires_reconciliation`; late workers
   cannot reissue terminal feedback or reuse captured results under a new
   epoch. Lost ACK is **not** evidence that Send was not applied.
5. Verify two browsers, two devices, rejoin-after-offline, browser/MV3 restart,
   stale Git source heads, unknown ACK, failed network, mid-Send cutover,
   parent-feedback and cleanup races. Require an operator-controlled live
   acceptance window with reversible stop semantics that never silently
   restores legacy authority.
6. Only then design trusted browser Send/ACK/result publication under the
   exact globally fenced epoch. Current implementation must remain OFF.

## Current operator limits and verification

Do not use Codex, GitHub Actions or the hosted runner budget. Never restart
Local Agent, change global Bridge Master, set a production suspension latch
or automatically promote a new Superchat. Source changes require exact-head
Mac/sandbox tests, with skipped tests reported unverified, not passing.
Existing completed tests on #209/#214/#239 are historical evidence, not
proof of new cross-device retirement.

See `GITHUB_FIRST_CURRENT_HANDOFF.md`,
`GITHUB_FIRST_FINAL_SESSION_HANDOFF_20261009.md` on PR #240, and
`LOCAL_VERIFICATION.md`.
