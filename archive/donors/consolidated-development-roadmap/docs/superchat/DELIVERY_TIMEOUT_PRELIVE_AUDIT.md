# Assistant delivery-timeout pre-live audit

Status: candidate-only audit for `work/chat-delivery-timeout-detection`. This document is a release gate, not a claim that production `main` or the operator's installed Chat Bridge has been changed.

## Scope

The failure under test happens **after** ChatGPT has accepted a Bridge-authored user message and then renders an assistant-side terminal error:

```text
Message delivery timed out. Please try again.  [Retry]
```

It is not `delivery_unconfirmed`. The original user message already exists in the conversation and must never be submitted a second time. Recovery is therefore allowed to use only ChatGPT's existing Retry action for that assistant turn.

## Architecture and ownership

The candidate keeps recognition, authorization, action and scheduling separate:

1. `dom_contract.js` recognizes only the captured timeout structure and only when that timeout assistant message is the latest rendered conversation turn.
2. `exhaustion_guard.js` owns browser observation. It derives the triggering user turn, reports the typed error and never creates a replacement user message.
3. `worker_transport.js` validates extension sender/top-frame/exact conversation URL, owns content/guard protocol readiness and exposes live timeout state to wake delivery.
4. `worker_assistant_errors.js` owns Bridge-message ownership, exact preferred-tab enforcement, durable attempt accounting and retry authorization.
5. `worker_delivery.js` refuses a new wake while the live guard still reports an unresolved recoverable timeout.
6. `worker_conversations.js` clears retry history across rebind/remove/re-add lifecycle boundaries.
7. `worker_events.js` only routes Chrome events/messages; it does not contain recovery policy.

`service_worker.js` remains composition-only. The timeout policy therefore does not leak into executor, repository, scheduler or Local Agent daemon code.

## Authorization chain

An automatic Retry click requires every layer below to agree:

- sender is this extension;
- sender is the top frame;
- normalized sender URL equals the declared configured conversation URL;
- sender tab id equals the conversation's current `preferredTabId`;
- triggering user text begins with the exact hard-binding Bridge envelope/policy for that conversation;
- Master is enabled;
- conversation is enabled;
- binding revision is unchanged from error report to Retry authorization;
- conversation generation is unchanged from error report to Retry authorization;
- the same timeout snapshot and triggering user identity are still current immediately before the click;
- assistant is not currently generating;
- Retry button is still connected, enabled and visible.

Any failed check cancels the click. A second tab showing the same ChatGPT conversation cannot independently spend the retry budget because only the preferred delivery tab is authorized.

## Retry state

Chrome local storage key:

```text
bridgeAssistantErrorRecovery
```

The worker stores at most one current retry entry per configured chat and normalizes the storage envelope before every mutation. The effective retry identity contains:

```text
conversation URL
binding revision
triggering user identity
error kind
```

The attempt mutation is serialized inside the service worker, so overlapping authorizations cannot both observe the same previous count. The budget survives MV3 service-worker restart and is cleared on explicit rebind, remove and fresh re-add.

Current bounded delays:

```text
1 -> 1.5 s
2 -> 5 s
3 -> 15 s
```

After attempt 3 still leaves the same timeout unresolved, the next observation records `assistant_retry_exhausted`, disables only that conversation and clears its alarm. There is no fourth click and no fresh wake layered over the failed turn.

## Same-node / long-generation behavior

ChatGPT may reuse the same timeout DOM node while Retry begins generation. A fixed watchdog deadline is unsafe because a valid generation may exceed that deadline.

Guard v3 therefore uses an 8-second **minimum recheck grace**, not an 8-second completion deadline. After that grace the normal mutation/periodic scan loop continues waiting as long as a visible Stop control says generation is active. Only after generation stops may the unchanged timeout be reported again and consume the next delayed attempt.

This avoids both failure modes:

- rapid duplicate Retry clicks while generation is still active;
- permanent recovery stall merely because generation lasted longer than a fixed watchdog count.

## Wake-overlap protection

A scheduled or manual wake first probes the live assistant guard. If the latest turn is still the recoverable timeout, delivery returns:

```text
assistant_recovery_pending
```

No new Bridge user message is submitted. The preflight also sends a recovery kick to the exact preferred tab so a timeout that was previously left dormant by a Master/lifecycle transition can be scanned again. Once the live timeout is gone, ordinary delivery may continue.

This gate is intentionally based on current DOM state rather than only `lastStatus`, so a recovered answer does not need a fragile durable "success" journal before future wakes can resume.

## Worker/extension restart behavior

Two independent restart cases are covered:

- **MV3 service-worker restart:** attempt count remains in Chrome local storage and the next report resumes with the next delay rather than attempt 1.
- **extension/worker activation with an already-open tab:** worker startup probes both normal content protocol and assistant guard protocol. A current `content.js` with an old guard is no longer accepted as fully ready; only the stale guard is reinjected and re-probed.

Chat Bridge 0.5.10 retains content protocol v7 because ordinary submission semantics are unchanged. Assistant terminal-error observation has its own guard protocol v3.

## Negative/race matrix

The pre-live suite must continue proving all of these outcomes:

| Scenario | Required result |
| --- | --- |
| captured timeout is latest turn, Bridge-owned | bounded Retry eligible |
| timeout belongs to normal operator message | diagnostic only, no auto click |
| timeout card followed by newer user turn | stale, ignored |
| timeout card followed by newer assistant turn | stale, ignored |
| wrong conversation URL | rejected |
| same URL in non-preferred duplicate tab | rejected |
| binding revision changes during delay | authorization rejected |
| conversation generation changes during delay | authorization rejected |
| Master disabled before authorization | click cancelled |
| conversation disabled before authorization | click cancelled |
| Retry button disappears before click | no click |
| assistant starts generating before click | no click |
| same error node survives generation >8 s | wait, then continue bounded policy |
| three failed retries | disable chat, clear alarm, no fourth click |
| scheduled/manual wake while timeout unresolved | `assistant_recovery_pending`, no user submission |
| timeout resolves before next wake | normal wake may proceed |
| MV3 worker restarts after attempt 1/2 | durable attempt count preserved |
| extension reload leaves old guard in open tab | stale guard replaced automatically |
| rebind/remove/re-add | previous retry history cannot leak into new lifecycle |

## Sandbox reproduction

Verification has three layers:

1. Node contract/unit tests exercise DOM recognition, stale-turn rejection, exact-tab checks, lifecycle/generation rejection, durable attempts, restart persistence, lifecycle reset and unresolved-timeout wake gating.
2. The existing isolated Chromium smoke loads the **real unpacked extension** into a disposable offline browser profile, renders the captured timeout structure, submits one Bridge wake, lets the extension press Retry and verifies the original user message count remains exactly one.
3. The resilience Chromium smoke renders two additional fixtures: a stale timeout followed by a newer assistant turn, and a same timeout node retained across a generation longer than eight seconds. The latter must make exactly three Retry clicks, preserve one original user submission and finish fail-closed as `assistant_retry_exhausted`.

All browser fixtures run offline and do not touch the operator's ChatGPT account/profile.

## Live-only unknowns

No sandbox can prove behavior that belongs to the current ChatGPT production UI/server. These remain the explicit live-smoke boundary:

- whether production still renders `.text-token-text-error` for this failure;
- whether `regenerate-thread-error-button` remains the Retry control;
- whether production localization changes the English fallback text while the test id remains stable;
- whether production removes, replaces or reuses the timeout assistant node during Retry;
- exact visibility/Stop-button timing in the real page;
- server behavior when Retry itself fails repeatedly;
- ChatGPT synchronization behavior when the same conversation is open in multiple real tabs/devices.

Any DOM mismatch must fail closed: no automatic click is preferable to guessing.

## Pre-main live-smoke sequence

The safest live validation is against the exact final candidate worktree before advancing `main`:

1. Record production `main` SHA/tag and installed Bridge version.
2. Turn Bridge Master off.
3. Load/reload the candidate `chat_bridge` directory as the unpacked extension; do not restart Local Agent daemon merely for this browser-only candidate.
4. Confirm popup/DEBUG reports Chat Bridge 0.5.10 and content protocol v7.
5. Keep one bound non-consequential test conversation as the preferred tab.
6. Reproduce or wait for the real `Message delivery timed out` card.
7. Verify the extension clicks only Retry, never inserts a second user message, and state progresses through `assistant_delivery_timeout` / `assistant_retry_N` as applicable.
8. During one test, open the same conversation in a second tab and confirm only the preferred tab can recover it.
9. During one unresolved timeout, invoke `Run now` and confirm `assistant_recovery_pending` with no additional user turn.
10. Reload the extension while the timeout card remains and confirm recovery resumes without resetting the durable attempt budget.
11. Verify a normal operator-authored timed-out message is not automatically retried.
12. Verify the resolved conversation can send a later ordinary Bridge wake.
13. Re-enable normal Master scheduling only after those checks pass.

If any invariant fails, turn Master off first and reload the production 0.5.9 extension from the production checkout. Do not advance `main`.

## Release gate

Before an explicit decision to advance `main`, require all of the following on one exact final candidate SHA:

- focused Bridge validation green;
- full Python/unit/integration CI green;
- coverage job green;
- Python 3.14 job green;
- macOS smoke green;
- real isolated Chromium extension smoke green, including timeout resilience;
- final `main...candidate` architecture/diff review;
- release-note/changelog/version synchronization prepared as the release commit;
- production `main` left untouched until the operator explicitly approves the release.
