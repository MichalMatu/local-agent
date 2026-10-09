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

## Legacy browser effect-site inventory (2026-10-09 source review)

`chat_bridge/github_fabric_legacy_effect_inventory.test.js` is an
offline **review sentinel**, not runtime protection. It freezes a count
of 14 direct Chrome tabs/script API sites across six source modules, plus
legacy parent/child composer clicks and form submission. The inventory
includes:

| Source | Relevant effect boundaries |
| --- | --- |
| `worker_spawn.js` | two tab creates, one navigation, three tab messages (including readiness probe), one content-script injection |
| `worker_spawn_result.js` | result-observation tab message, fallback script injection, owned-tab removal |
| `worker_spawn_route_transition.js` | two direct script injections and one non-Send DOM expander click |
| `worker_delivery.js` | parent-feedback message and in-tab DOM observation script |
| `spawn_content.js` | two bootstrap Send button clicks (legacy and V2) |
| `content.js` | parent composer Send button click and `requestSubmit` fallback |

The terminal-feedback claim wrapper lives in
`worker_conversation_fabric_delivery_guard.js`, while child effect lifecycle
state is coordinated in `worker_conversation_fabric.js`. A changed source
site count is a review failure, not automatic permission; moving an effect
without changing counts can evade this sentinel, and old/offline extension
copies are wholly outside it. Future global arbitration has to cover every
effect above, including the **actual page-side submit** and parent terminal
feedback, before new-mode admission is even considered.

Source-only snapshot continuity now flags missing previously declared
workers, lost effect records, effect identity rewrites, changes to terminal
receipts, unknown outcomes relabeled as success, in-flight effects reset to
prepared, and unverifiable retirement receipts. These diagnostics are
conservative and always return `blocked`, even if evidence is complete.
They do not attest actual browser side effects or revoke old sessions.

## Source-only effect journal verifier (new draft follow-up)

`chat_bridge/github_fabric_effect_journal_audit.js` implements a bounded
hash-chained **forensic reader**, not a publisher or live admission system.
For each canonical parent, ordered events reference an exact effect identity,
request digest, worker, transport, epoch and one of `prepared`,
`effect_started`, `ack_observed` or `effect_unknown`.

The reader now requires `inspectEffectJournal(journal, trustedAnchor)`.
The **separately supplied** strict anchor binds the parent, fence epoch,
Git commit SHA, expected head digest and event count. Missing, malformed,
stale, forked or conflicting anchors fail closed before journal verification.
The caller must acquire the anchor from an **authenticated commit-pinned
GitHub read** independently of the journal; this pure module can only compare
fields and cannot verify its provenance or the Git commit itself.
The reader enforces contiguous sequences starting at 1, SHA-256 hashes of
canonical event tuples, an explicit expected head digest and expected count,
fixed parent and bounded epoch, immutable per-effect identity, unique
preparation and lifecycle transitions. It refuses missing/rewritten entries,
truncated pinned history, replacement workers/modes/request digests, ACK
without an earlier effect-start event, automatic downgrades and any transition
out of `effect_unknown` or `ack_observed`. The empty journal remains blocked.

An `ack_observed` event is only a **reported observation** and is exposed as
`ack_claim_for_review`, not a trusted ChatGPT Send acknowledgment.
`effect_unknown` and incomplete phases remain
`suspended_requires_reconciliation`. **All results have
`browser_effects_permitted=false` and `automatic_retry_permitted=false`.**
Even a fully hashed journal cannot prove that an uninstrumented old extension
did not act. The hash chain detects corruption relative to an externally
trusted anchor; it is **not** a signature, source authenticity mechanism,
complete browser inventory or anti-fork CAS by itself. A caller supplying
both a journal and an invented anchor can generate a self-consistent fiction.
No live journal persistence or private `parents/` write is introduced.

Unit coverage includes deleted tail/middle events, rewritten messages, bad
sequence/identity, changed actor/epoch/request, missing pre-Send transition,
duplicate send phases, lost ACK, two-device overlapping claims, attempted
unknown-to-ACK upgrade, malformed input and bounded exhaustion. When two
distinct effect IDs claim the same canonical request digest and kind, the
reader reports `duplicate_logical_request_effect` even across devices and
modes. This is a review finding, not proof that the second attempt was a
replay: request digests must actually bind stable logical request identity.
Both still receive no permission to replay. The reader and tests are not
imported by production Chrome code.

## Migration decision: in-place takeover vs. isolated new parent

**In-place takeover of the existing parent URL is blocked.** An older
uncooperative Chrome extension can still drive that DOM, including after
returning from offline, regardless of a GitHub CAS, local storage marker,
journal receipt or lease expiry. Merely uninstalling/reloading the extension
on the Mac does not revoke an unknown other browser. We have no remote
effect-time enforcement primitive that can authorize same-parent takeover.

A potential **separate-parent manual continuity** workflow is not a takeover:

1. Keep the old parent identity and all uncertain child effects intact.
   Existing legacy Chrome delegation continues on its existing parent.
   Never silently mark ambiguous results as successfully delivered.
2. The operator explicitly creates an unrelated new ChatGPT parent session,
   with a fresh canonical URL and separate parent identifier. It only
   **reads** authorized durable workflow data from GitHub and surfaces the
   last confirmed checkpoint plus unresolved effects. No old campaign
   mutation, automatic child creation or browser Send is implied.
3. Before considering any automated effect on that new parent, independently
   demonstrate that **no legacy worker can target it**, including
   automatic onboarding, another browser, rejoined offline installations
   and stale content scripts. If this cannot be proven, the new parent stays
   read-only/manual. A new URL alone is NOT an exclusion guarantee.
4. Keep the legacy parent active until deliberate human retirement is
   operationally safe; retiring the old parent requires explicit operator
   inventory of affected browsers and a verified, persistent effect-enforcing
   revocation boundary. Neither an installation list nor browser ACK alone
   suffices for a same-parent cutover.
5. Do not auto-migrate, merge, replay or alias historical effect IDs or
   terminal feedback between parent identities. Rollback is an explicit
   user choice with separate effect reconciliation, not deleting a local
   marker or decrementing the epoch.

**Possible future enforcers to evaluate** include an externally enforced
browser extension disablement policy that remains effective for offline
and rejoining clients, or a product-controlled effect gateway through
which all possible browser drivers must pass. Each requires proving that
old builds cannot bypass enforcement. Standard Chrome DOM actions do not
pass through the GitHub/local-agent control plane, so neither option is
implemented today. The default decision is **deny**.

This distinction lets us continue safe GitHub-first *read-only project
rehydration* and manual handoff without pretending that GitHub-first
**browser Send/ACK** or cross-device automatic delegation is production ready.

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
