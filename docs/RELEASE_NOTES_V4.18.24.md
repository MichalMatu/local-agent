# Local Agent 4.18.24

## Summary

Prepare Chat Bridge 0.5.10 to recover a captured ChatGPT assistant-side `Message delivery timed out. Please try again.` failure without duplicating the already-accepted Bridge user message.

The recovery path is intentionally browser-only. Local Agent executor, repository admission, task schema, hard-binding schema, resource scheduling, supervisor process lifecycle and daemon behavior are unchanged.

## Assistant timeout recovery

ChatGPT can accept the submitted Bridge user message and later render a terminal assistant error containing a native Retry control. This is not `delivery_unconfirmed`: the original user turn already exists and must not be submitted again.

Chat Bridge 0.5.10 therefore:

- recognizes only the captured `.text-token-text-error` timeout shape when it is the latest rendered conversation turn;
- requires the triggering user turn to be Bridge-owned before automatic recovery;
- refuses to adopt a retained pre-bootstrap timeout into a fresh binding lifecycle;
- requires the reporting tab to be the configured conversation's exact preferred delivery tab;
- revalidates binding revision and conversation generation between error report and Retry authorization;
- fences terminal retry exhaustion by both binding revision and conversation generation;
- clicks ChatGPT's existing Retry control rather than inserting a new user prompt;
- persists a bounded three-attempt retry budget in Chrome local storage with 1.5 s, 5 s and 15 s delays;
- survives MV3 service-worker restart without resetting the retry budget;
- clears stale retry history across rebind/remove/re-add lifecycle boundaries;
- disables only the affected conversation and clears its alarm after the third unresolved Retry.

A timeout after a normal operator-authored message is diagnostic-only and is never automatically clicked.

## Same-node and wake-overlap hardening

ChatGPT may reuse the same timeout DOM node while Retry begins generation. Guard protocol v3 treats eight seconds as a minimum recheck grace, not a completion deadline, and continues waiting while a visible Stop control indicates active generation.

Before any scheduled or manual wake, the worker probes the live guard. An unresolved timeout returns `assistant_recovery_pending` and blocks a fresh Bridge user message. Once the live timeout is no longer current, normal delivery may continue.

This prevents a busy-retry alarm or manual `Run now` from layering a new wake over the failed turn while still avoiding a separate durable success journal.

## Extension update behavior

Chat Bridge advances from 0.5.9 to 0.5.10. Ordinary content protocol remains v7 because normal submission semantics are unchanged. Assistant timeout/exhaustion observation has an independent guard protocol v3.

Worker activation now probes both normal content and the assistant guard for already-open configured tabs. A current `content.js` paired with a stale guard is no longer treated as ready; the stale guard is reinjected and re-probed without requiring a normal ChatGPT page reload.

## Verification

Focused tests cover captured-DOM recognition, stale-card rejection, operator-owned negative cases, duplicate-tab rejection, Master/disabled-chat cancellation, binding/generation races, stale-generation exhaustion rejection, fresh-bootstrap lifecycle boundaries, durable retry accounting, worker restart persistence, lifecycle reset, stale-guard refresh, wake gating and fail-closed exhaustion.

Isolated Chromium smoke loads the real unpacked extension in an offline disposable profile. It verifies:

- one Bridge user submission followed by the captured timeout and one native Retry recovery;
- no duplicate user submission;
- stale timeout cards behind newer turns are ignored;
- the same timeout node can remain through a generation longer than eight seconds;
- exactly three bounded Retry clicks occur before fail-closed exhaustion when the error never resolves;
- a timeout after a normal operator-authored message is diagnostic-only, never auto-clicked, blocks overlapping `Run now`, and allows normal wake delivery again after the stale error card is gone.

The full pre-live matrix is recorded in `docs/superchat/DELIVERY_TIMEOUT_PRELIVE_AUDIT.md`; the final second-pass review is recorded in `docs/superchat/DELIVERY_TIMEOUT_REAUDIT.md`.

## Release boundary

These notes describe the prepared 4.18.24 candidate. They do not by themselves advance production `main`, change the installed operator extension or restart the Local Agent daemon.

Release acceptance requires one exact final candidate SHA with all CI jobs green, the isolated browser resilience smoke green, a final `main...candidate` architecture/diff review, and one controlled live ChatGPT browser smoke against the candidate before the explicit production release decision.
