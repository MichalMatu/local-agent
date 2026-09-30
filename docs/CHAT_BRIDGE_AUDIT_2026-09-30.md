# Chat Bridge 0.6.0 independent post-release audit — 2026-09-30

## Scope and baseline

This audit starts from `main` / tag `v4.19.9` at `428dc37d2e66179c6368aa2a2bd53063445a4fd2`. The original dated Chat Bridge handoff was used as historical input together with the source/test files it named; after the audit its durable conclusions were folded into this document and `GITHUB_BRIDGE_CONTROL.md`, so the transient handoff itself is no longer part of the current documentation set.

Audited areas:

- GitHub-backed `conversation_controls` architecture;
- race conditions and generation/idempotence boundaries;
- Manifest V3 worker/alarm lifecycle;
- two independent Chrome profiles;
- runtime cache and polling behavior;
- popup schedule ownership;
- legacy LAB compatibility surface;
- security validation of remote desired state;
- wake composer/Send submission path.

The final production-shaped validation used the daily Chrome profile and exact conversation `chat-be9defd7`, bound to `MichalMatu/local-agent` at binding revision 1. The test ended at control generation 3 with `enabled=false` and `next_wake_at=null`.

## Findings

### High: concurrent reconcile can apply one remote generation twice

`bridgeState` writes are serialized, but the 0.6.0 GitHub reconcile operation was not. Two activation/popup/alarm paths could read the same old applied-generation journal before either completed, then each enter the serialized state mutation believing the same remote generation was fresh. The result could increment `localGeneration` twice, churn alarms and invalidate an already-authorized delivery.

Accepted fix: serialize the complete GitHub reconcile transaction within one MV3 worker instance and test concurrent calls directly.

### High: cached or already-in-flight runtime reads can hide a just-published PAUSE at wake time

The conversation alarm correctly reconciles GitHub state before delivery, but 0.6.0 used the same 30-second cache and in-flight request de-duplication as ordinary configuration lookups. A control-boundary reconcile could therefore receive state fetched before a newly published `PAUSE`.

Accepted fix: control-boundary reads bypass both the cache and older in-flight configuration requests. Fetch sequencing prevents an older request that completes later from overwriting a newer control-boundary result in the cache.

### High: two Chrome profiles do not share a delivery lease

Applied-generation state, `chrome.alarms`, the configured preferred tab and `inFlightDeliveries` are profile-local. Two profiles configured for the same managed conversation can both accept the same still-future generation and both submit the same wake.

This is not safely fixable by another local boolean or DOM heuristic. Exactly-once cross-profile delivery would require shared authority: for example, an explicit desired-state executor/profile owner or another writable shared lease/acknowledgement service.

Operational decision: the supported production topology is one active normal Chrome-profile executor per managed conversation. Additional Chrome profiles may exist for diagnostic/Chrome Dev work, but they must not concurrently own/execute wakes for the same managed conversation outside a bounded test. The known second profile in the current deployment is diagnostic, not a second production executor, so a distributed lease is not a release requirement for this topology.

### High: a fresh profile can replay an already-expired one-shot

0.6.0 treated a remote generation unseen by the local profile as fresh. When its explicit `next_wake_at` was already in the past, `scheduleDeadline()` converted it to approximately `now+1s`. A new or previously unused profile could therefore replay a consumed historical NEXT.

Accepted fix: an expired one-shot always falls back to normal interval scheduling, including first observation on a cold profile.

### High: one generation was not actually immutable

The contract says every desired-state mutation increments `control_generation`, but the applied journal stored only generation/revision/local generation. If the remote payload changed under the same generation, the worker could confuse that unversioned remote rewrite with local drift and apply it.

Accepted fix: persist a canonical signature of the applied desired-state payload. A same-generation rewrite now fails closed, and a lower remote generation is treated as rollback rather than becoming popup authority.

### Medium: temporary remote record omission can hand ownership back to local/legacy pacing

0.6.0 retained sticky ownership only when the remote runtime was unavailable. A successfully fetched runtime that temporarily omitted the exact control record returned no GitHub authority, allowing local/legacy pacing to mutate state again.

Accepted fix: once a matching control has been applied for the current binding revision, ownership remains sticky across network failure, malformed publication, record omission, rollback and same-generation conflict. Rebind creates a new revision. Explicit Remove clears the durable applied-ownership entry so a later re-add starts cleanly.

### Medium: popup pacing controls imply authority they no longer own

The popup still rendered an active enable switch and editable interval for a GitHub-managed chat. A local edit could be accepted, increment local generation and then be repaired by the next remote reconcile. During an outage or stale remote publication the UI could also diverge from the worker's sticky ownership decision.

Accepted fix: managed per-conversation enable and interval controls are read-only with a `GitHub managed` badge; the worker independently rejects direct local pacing writes. Popup state is filtered through the applied ownership snapshot so rollback/conflicting remote records are not displayed as authoritative. Master, `Run now`, binding/removal and diagnostics remain local operator actions.

### Medium: remote one-shot timestamp relationships were under-constrained

The model validated timestamp syntax but not desired-state consistency. A disabled record could carry a wake deadline; a deadline could precede `updated_at`; and a one-shot could be arbitrarily far away.

Accepted fix: require `next_wake_at=null` while disabled, require a one-shot not to precede `updated_at`, and cap the one-shot horizon at 24 hours to match the existing bounded NEXT contract. Application-time validation also rejects an otherwise syntactically valid deadline that is now more than 24 hours in the future.

### Medium: managed STATUS still had a competing DOM feedback path

Although documentation made GitHub authoritative for `STATUS`, `[LAB:STATUS]` still reached legacy local inspection feedback on a managed chat.

Accepted fix: treat managed assistant STATUS as `github_control_managed` compatibility no-op. This does not restore assistant LAB scheduling; it removes a competing status transport.

### Security assessment

The remote desired state is untrusted input but is bounded by exact conversation/repository/binding/revision matching, type/range validation, timestamp bounds and immutable-generation checks. The extension has no GitHub credential and cannot write the control plane. Manifest host permissions are limited to ChatGPT/OpenAI conversation hosts and `raw.githubusercontent.com`; popup-only mutating messages are gated by extension id and exact popup URL, while content-origin actions are revalidated in their handlers.

`runtimeUrl` itself is stored as a string rather than allowlisted in state-model code, but MV3 host permissions already prevent fetches outside the declared remote host set. This is a defense-in-depth cleanup opportunity rather than an active privilege expansion in 0.6.0.

### Cleanup: legacy DOM code remains larger than the current authority surface

Assistant/grouped-turn scanning remains useful for migration binding, maintenance, recovery and diagnostics, but browser regression coverage is still dominated by historical schedule-marker cases. No new schedule heuristic should be added there. A later cleanup can split retained migration/diagnostic scanning from obsolete pacing-oriented compatibility tests after the GitHub control plane has aged in production.

### Wake submission path: no speculative behavior change

The current delivery boundary has the correct safety shape: exact conversation, no active Stop state, exact composer ownership, worker authorization, live Send re-resolution, live click with bounded `requestSubmit()` fallback, and exact new-user-turn confirmation.

The v4.19.9 field evidence included one observation where Bridge text remained in the composer without submission. That is evidence of a real field anomaly, but not enough to prove whether the failure is React state readiness, click handling, node replacement or another renderer condition. A second automatic click or fallback submit without a demonstrated root cause risks duplicate user turns.

Decision: leave submit behavior unchanged. Improve only when a reproducible capture can distinguish pre-submit no-op from accepted-but-unconfirmed delivery.

## MV3 lifecycle assessment

The architecture correctly uses durable `chrome.alarms` rather than timers for worker-independent discovery and registers listeners synchronously through the service-worker composition path. Ensuring the poll alarm on activation/install/startup is appropriate because MV3 service workers are non-persistent and alarm persistence across extension/browser lifecycle is not a sufficient sole invariant on the supported Chrome baseline.

The one-minute poll is not a real-time deadline guarantee. Chrome may delay alarms; correctness must therefore come from desired-state generation and exact delivery revalidation, not from assuming a poll fires on the exact minute.

The applied-generation journal remains a separate `chrome.storage.local` record from `bridgeState`. A worker termination between state mutation/alarm repair and acknowledgement write can cause harmless re-application/generation churn after restart, although the shared alarm name and generation guards keep the delivery path fail-closed. Folding acknowledgement metadata into one atomic state transaction is a future simplification candidate, not required for this hardening branch.

## Implemented hardening

Branch: `audit/chat-bridge-0.6.0-hardening`

Implemented:

- full reconcile serialization;
- truly fresh, monotonic control-boundary runtime fetches;
- cold-profile expired NEXT fallback;
- immutable desired-state generations and rollback rejection;
- sticky applied ownership on missing/conflicting/stale remote state;
- explicit ownership reset on Remove;
- Remove/Rebind serialization against reconcile;
- desired-state timestamp/horizon validation before local state mutation;
- managed STATUS compatibility no-op;
- managed popup pacing read-only state plus worker-side mutation guard;
- focused race/cache/cold-profile/generation/Master/ownership regressions.

Intentionally not implemented:

- cross-profile shared executor/lease, because the supported deployment uses one production profile and the second profile is diagnostic only;
- speculative wake-submit retry/double-click behavior;
- broad deletion of legacy DOM compatibility before the new control plane has a post-release validation cycle;
- state/journal co-location, because it is a larger persistence migration with no demonstrated duplicate-delivery failure in the current generation-guarded path.

## Production-shaped E2E

The final release gate was executed on 2026-09-30 in the normal/daily Chrome profile against conversation `chat-be9defd7` bound to `MichalMatu/local-agent` with binding revision 1.

The first attempted test publication targeted an older conversation id and was therefore correctly ignored by the worker's exact identity matching. That was test-setup error, not a Bridge delivery failure. The stale test record was returned to `PAUSED` before continuing.

The clean run then used the exact active conversation:

1. generation 1 established the matching GitHub-owned record in `PAUSED` state;
2. manual `Run now` was used only to prove the local binding/submit path and returned the exact `chat-be9defd7` / `local-agent` binding envelope;
3. generation 2 armed a single `NEXT` for `2026-09-30T05:02:00+02:00`;
4. without `Run now` or LAB schedule transport, the automatic wake appeared at approximately `05:02:07+02:00` with the exact `chat-be9defd7` / `local-agent` envelope;
5. generation 3 immediately returned desired state to `PAUSED` with `enabled=false` and `next_wake_at=null`.

This validates the production-shaped GitHub desired state -> MV3 reconcile -> `chrome.alarms` -> exact conversation -> composer/Send submission path on the supported single-production-profile topology.

## Verification and release implication

The implementation candidate `04026aefc22c4a8aa7198675e2a4378a5ea3ecd6` passed the complete five-job CI matrix, including browser and macOS smoke. The documentation-cleanup head `0614c0b26f3cf93666d56caf65914c0d7eb14994` also passed all five jobs in CI run `36660061302`.

The bounded production-shaped Chat Bridge control E2E is now complete and ended `PAUSED`. The production gate that kept PR #118 in draft is therefore satisfied. The final documentation commit still requires its own CI result before merge.

No assistant LAB schedule transport is restored by this branch.
