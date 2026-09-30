# Chat Bridge 0.6.0 independent post-release audit — 2026-09-30

## Scope and baseline

This audit starts from `main` / tag `v4.19.9` at `428dc37d2e66179c6368aa2a2bd53063445a4fd2` and treats current source plus `CHAT_BRIDGE_HANDOFF_2026-09-30.md` as the baseline evidence.

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

The live production desired state was verified separately to remain generation 4 `PAUSED`, with `next_wake_at=null`. This candidate does not modify `chat-bridge-state`.

## Findings

### High: concurrent reconcile can apply one remote generation twice

`bridgeState` writes are serialized, but the 0.6.0 GitHub reconcile operation was not. Two activation/popup/alarm paths could read the same old applied-generation journal before either completed, then each enter the serialized state mutation believing the same remote generation was fresh. The result could increment `localGeneration` twice, churn alarms and invalidate an already-authorized delivery.

Candidate fix: serialize the complete GitHub reconcile transaction within one MV3 worker instance and test concurrent calls directly.

### High: the 30-second runtime cache can hide a just-published PAUSE at wake time

The conversation alarm correctly reconciles GitHub state before delivery, but 0.6.0 used the same cached runtime read as ordinary configuration lookups. A remote `PAUSE` published shortly after the cache was populated could therefore be missed at the exact delivery boundary.

Candidate fix: control-boundary reconciliation and managed legacy-authority checks perform fresh remote reads while retaining request de-duplication for an already in-flight fetch.

### High: two Chrome profiles do not share a delivery lease

Applied-generation state, `chrome.alarms`, the configured preferred tab and `inFlightDeliveries` are profile-local. Two profiles configured for the same managed conversation can both accept the same still-future generation and both submit the same wake.

This is not safely fixable by another local boolean or DOM heuristic. Exactly-once cross-profile delivery requires shared authority: for example, an explicit desired-state executor/profile owner or another writable shared lease/acknowledgement service.

Candidate decision: document this as an explicit architectural constraint and do not pretend local dedupe solves it. One managed conversation must currently have one active Chrome-profile executor.

### High: a fresh profile can replay an already-expired one-shot

0.6.0 treated a remote generation unseen by the local profile as fresh. When its explicit `next_wake_at` was already in the past, `scheduleDeadline()` converted it to approximately `now+1s`. A new or previously unused profile could therefore replay a consumed historical NEXT.

Candidate fix: an expired one-shot always falls back to normal interval scheduling, including first observation on a cold profile.

### Medium: temporary remote record omission can hand ownership back to local/legacy pacing

0.6.0 retained sticky ownership only when the remote runtime was unavailable. A successfully fetched runtime that temporarily omitted the exact control record returned no GitHub authority, allowing local/legacy pacing to mutate state again.

Candidate fix: once a matching control has been applied for the current binding revision, ownership remains sticky across network failure, malformed publication and missing-record publication. Explicit Rebind creates the boundary that exits that generation space.

### Medium: popup pacing controls imply authority they no longer own

The popup still rendered an active enable switch and editable interval for a GitHub-managed chat. A local edit could be accepted, increment local generation and then be repaired by the next remote reconcile.

Candidate fix: exact managed records render per-conversation enable and interval as read-only with a `GitHub managed` badge. Master, `Run now`, binding/removal and diagnostics remain local operator actions.

### Medium: remote one-shot timestamp relationships were under-constrained

The model validated timestamp syntax but not desired-state consistency. A disabled record could carry a wake deadline; a deadline could precede `updated_at`; and a one-shot could be arbitrarily far away.

Candidate fix: require `next_wake_at=null` while disabled, require a one-shot not to precede `updated_at`, and cap the one-shot horizon at 24 hours to match the existing bounded NEXT contract.

### Medium: managed STATUS still had a competing DOM feedback path

Although documentation made GitHub authoritative for `STATUS`, `[LAB:STATUS]` still reached legacy local inspection feedback on a managed chat.

Candidate fix: treat managed assistant STATUS as `github_control_managed` compatibility no-op. This does not restore assistant LAB scheduling; it removes a competing status transport.

### Cleanup: legacy DOM code remains larger than the current authority surface

Assistant/grouped-turn scanning remains useful for migration binding, maintenance and diagnostics, but browser regression coverage is still dominated by historical schedule-marker cases. No new schedule heuristic should be added there. A later cleanup can split retained migration/diagnostic scanning from obsolete pacing-oriented compatibility tests after the GitHub control plane has aged in production.

### Wake submission path: no speculative behavior change

The current delivery boundary has the correct safety shape: exact conversation, no active Stop state, exact composer ownership, worker authorization, live Send re-resolution, live click with bounded `requestSubmit()` fallback, and exact new-user-turn confirmation.

The release handoff records one live observation where Bridge text remained in the composer without submission. That is evidence of a real field anomaly, but not enough to prove whether the failure is React state readiness, click handling, node replacement or another renderer condition. A second automatic click or fallback submit without a demonstrated root cause risks duplicate user turns.

Candidate decision: leave submit behavior unchanged. Improve only when a reproducible capture can distinguish pre-submit no-op from accepted-but-unconfirmed delivery.

## MV3 lifecycle assessment

The architecture correctly uses durable `chrome.alarms` rather than timers for worker-independent discovery and registers listeners synchronously through the service-worker composition path. Ensuring the poll alarm on activation/install/startup is appropriate because MV3 service workers are non-persistent and alarm persistence across extension/browser lifecycle is not a sufficient sole invariant on the supported Chrome baseline.

The one-minute poll is not a real-time deadline guarantee. Chrome may delay alarms; correctness must therefore come from desired-state generation and exact delivery revalidation, not from assuming a poll fires on the exact minute.

## Candidate implementation

Branch: `audit/chat-bridge-0.6.0-hardening`

Implemented:

- full reconcile serialization;
- fresh runtime fetch at control reconcile/authority boundaries;
- cold-profile expired NEXT fallback;
- sticky applied ownership on missing remote record;
- desired-state timestamp/horizon validation;
- managed STATUS compatibility no-op;
- managed popup pacing read-only state;
- focused race/cache/cold-profile/Master/ownership regressions.

Intentionally not implemented:

- cross-profile shared executor/lease, because it requires a reviewed shared authority contract;
- speculative wake-submit retry/double-click behavior;
- broad deletion of legacy DOM compatibility before the new control plane has a post-release validation cycle.

## Release implications

This branch changes runtime behavior and is not production merely because focused tests pass. Before advancing `main`, repository policy still requires exact-candidate CI, macOS smoke, browser smoke and a bounded production-shaped Chat Bridge control E2E ending PAUSED. A release/version decision should be made only after those gates are green.
