# Chat Bridge field-test handoff — 2026-09-29

This handoff is the canonical continuation point for the long 2026-09-29 Chat Bridge diagnostic session. It intentionally separates **confirmed evidence** from hypotheses that were later disproved or superseded.

Do not reconstruct the debugging history from old chat messages or intermediate release notes. Start from the production state below and perform the remaining live acceptance test.

## Production state

```text
Local Agent release: v4.19.8
production main:     7b436126cb2029d8757a38c32b31ed8e1e7430e2
release tag:         v4.19.8 -> 7b436126cb2029d8757a38c32b31ed8e1e7430e2
Chat Bridge:         0.5.18
content protocol:    v13
assistant guard:     v8
```

At handoff time the `host-ops` daemon also reports `daemon_version=4.19.8`, `self_revision=7b436126cb2029d8757a38c32b31ed8e1e7430e2`, execution model `multi_repository_worker`, and idle state.

Release 4.19.8 includes the final fixes from PRs #112/#113 and the macOS control-admission test stabilization that preceded final release.

## Exact field-test environment

Canonical ChatGPT conversation:

```text
https://chatgpt.com/c/6aba8e87-80e4-83eb-84bd-f7d65a577d1e
```

Bridge conversation id observed in the successful wake:

```text
chat-a222afb6
```

Canonical conversation binding:

```text
repository id: host-ops
repository:    MichalMatu/host-ops
agent_binding: 16d688b6-b0ef-4905-a5bd-24e59c99cfb4
planner_scope: multirepo
```

Dedicated diagnostic Chrome-for-Testing profile:

```text
~/.local/share/local-agent/chat-bridge-cft
```

Chrome-for-Testing alias used during the session:

```text
~/.local/share/local-agent/chrome-for-testing/current
```

Do not touch the user's daily Chrome profile. Do not touch the older rollback profile `~/.local/share/local-agent/chat-bridge-chrome` unless the operator explicitly requests rollback work.

Resolve the current managed CDP endpoint and target id dynamically. Never reuse an endpoint/target id from this handoff after a browser restart.

## What was proven before v4.19.8

### Binding/storage/scheduler delivery path is real

After a stale-extension mismatch was repaired, manual popup **Add current chat** to `host-ops` succeeded. The popup showed the configured conversation and conservative paused state.

Manual `Run now` then successfully delivered a Bridge wake into the same canonical conversation. The wake included the exact host-ops envelope and `LA_CHAT=chat-a222afb6`.

Therefore the following boundary was already proven before the final renderer fix:

```text
popup -> worker -> storage -> scheduler -> content delivery -> same ChatGPT conversation
```

The remaining failure was specifically the **assistant response control scanner**.

### Assistant controls were not reaching the worker

`[LAB:RESUME]`, `[LAB:STATUS]` and `[LAB:PAUSE]` produced no Bridge feedback/state mutation even though `Run now` worked.

A before/after storage observation around `[LAB:PAUSE]` showed no new `lastControlAction`, no `lastControlAt`, and no `paused_by_assistant`. This proved the failure was before worker control application.

## Confirmed root causes found during the session

### 1. Stale MV3 service-worker runtime

One real failure was a split-version extension runtime:

```text
page/content scripts: newer protocol
MV3 service-worker cache: older protocol
```

The popup reported `content_script_protocol_mismatch`. A normal ChatGPT page reload did not replace the stale MV3 worker. Clearing/restarting only the dedicated diagnostic CfT extension runtime restored protocol agreement and manual Add succeeded.

Operational rule: **page reload is not extension-runtime reload**. After unpacked-extension source/protocol changes, verify worker/content/guard versions independently.

### 2. Mixed explicit/grouped assistant DOM

A staged renderer could leave older explicit assistant nodes while newer assistant responses used grouped turns. Selecting only explicit nodes whenever any explicit node existed hid newer answers.

The corrected contract merges explicit and grouped representations by logical turn and document order; explicit representation wins only inside the same logical turn.

### 3. User-only grouped turn shadowing

A grouped turn containing only a new user bubble could previously become the newest assistant candidate and shadow the preceding assistant control before the scanner fired.

The corrected scanner removes user bubbles/action controls and requires residual assistant text or a typed assistant error.

### 4. Assistant-only grouped turn

This was the decisive live root cause for the still-broken assistant LAB controls.

Live DOM inspection showed:

- six `data-turn-key` turns;
- five user bubbles;
- only three explicit assistant-role nodes;
- one logical turn with **no user bubble and no explicit assistant-role marker**, but real assistant paragraph content and action buttons.

The old grouped fallback required a user bubble, so this newest assistant response was completely invisible to the scanner.

v4.19.8 removes that assumption. An assistant-only `data-turn-key` is now eligible when bounded sanitization leaves residual assistant content or a recognized structured assistant error.

### 5. `Resume stream unavailable`

The field session captured a ChatGPT terminal card:

```text
Resume stream unavailable
[Retry]
```

The previous guard recognized only `Message delivery timed out. Please try again.` and therefore ignored this card.

v4.19.8 recognizes a second typed error kind `resume_stream_unavailable` and maps it to status `assistant_resume_stream_unavailable`. It uses the same exact-tab, Bridge-owned, binding/generation-checked native Retry path and the same three-attempt budget.

Do **not** claim that the observed `Resume stream unavailable` was definitely caused by a diagnostic browser restart. That causal hypothesis was not proven. What is proven is that external recovery/managed stop previously had no active-generation preflight, so v4.19.8 also makes those helpers refuse reload/stop while a visible ChatGPT Stop control exists unless explicit `--force` is used.

## Retired assumptions — do not reintroduce

The following statements are false or too broad:

- "A grouped assistant turn always contains a user bubble." — false.
- "If any explicit assistant node exists, grouped assistant turns can be ignored." — false.
- "A user-only grouped shell is a valid assistant candidate." — false.
- "Reloading the ChatGPT page refreshes an unpacked MV3 service worker." — false.
- "`worker_inactive` by itself means Bridge is broken." — false; MV3 workers may be inactive normally.
- "Because assistant LAB controls failed, binding/storage/scheduler must also be broken." — false; `Run now` already proved that path.
- "`content_script_protocol_mismatch` necessarily means the page content script is stale." — false; the worker itself can be stale.
- "Assistant controls cannot mutate conversation binding." — false in the current protocol. Explicit assistant `[LAB:ADD]`, `[LAB:REBIND]` and `[LAB:REMOVE]` are supported, exact-id validated and persistently deduplicated.
- "A ChatGPT conversation binding equals the only repository a multirepo planner may touch." — false. A `host-ops` multirepo conversation stays bound to host-ops while individual Local Agent tasks use the exact binding of each target catalog repository.
- "`Resume stream unavailable` should be recovered by resubmitting the previous user prompt." — false. Use ChatGPT's native Retry only after Bridge ownership authorization.

## Documentation cleanup performed with this handoff

`chat_bridge/README.md` was reduced to the current control/runtime contract and now explicitly documents assistant binding mutations, the multirepo distinction, assistant-only grouped turns, MV3 update semantics and both typed terminal errors.

`docs/CHATGPT_DOM_CONTRACT.md` was reduced to the implemented DOM contract. Historical 0.5.16-specific duplicate text and speculative future automatic "superchat rollover" design were removed from the canonical contract.

Historical release notes remain historical evidence and should not be rewritten to pretend they described later behavior.

## Remaining work: final live acceptance test

The final v4.19.8 source, tag and daemon are established. The remaining task is a **live E2E acceptance test on the same canonical CfT conversation** after final release.

Do not make another runtime patch before this test fails with new evidence.

### Step 1 — inspect only

Before any reload or mutation:

1. resolve the dedicated `chat-bridge-cft` managed endpoint dynamically;
2. require exactly one page target for the canonical conversation URL;
3. check for visible `stop-button` / `composer-stop-button` first;
4. if generation is active, do not recover/reload/stop the browser;
5. verify source/extension state:
   - Local Agent 4.19.8;
   - Chat Bridge 0.5.18;
   - content protocol 13;
   - assistant guard 8;
   - expected content-script fingerprints matched;
   - worker diagnostics have no relevant errors.

`worker_inactive` alone is acceptable. A version mismatch is not.

### Step 2 — inspect the existing conversation state

The operator intentionally paused the conversation during debugging to avoid repeated wakes. Do not assume it is still paused or enabled: read the current Bridge state/popup first.

Preserve the existing host-ops binding and extension storage. Do not remove/re-add the conversation unless evidence specifically requires testing that path.

### Step 3 — prove assistant control delivery one command at a time

Start with a read-only control:

```text
[LAB:STATUS]
```

Expected result: Bridge inserts a user-authored feedback message beginning with:

```text
[LA_BRIDGE_FEEDBACK]
command=STATUS
```

Do not send the next command until this feedback is observed or a diagnostic snapshot proves why it did not occur.

If STATUS succeeds, test state transitions sequentially:

```text
[LAB:RESUME]
[LAB:STATUS]
[LAB:NEXT=2m]
[LAB:STATUS]
[LAB:PAUSE]
[LAB:STATUS]
```

`NEXT=30s` remains protocol-compatible but is unnecessary for normal acceptance and can create avoidable wake spam. Prefer 2 minutes unless the operator explicitly asks to test the 30-second compatibility floor.

The final PAUSE should leave the diagnostic chat quiet.

### Step 4 — optional final wake proof

Only after assistant controls are proven, use one manual `Run now` if a final post-release wake proof is desired. Confirm the wake lands in the same canonical conversation and preserves the host-ops envelope. Then pause again.

Do not intentionally manufacture `Resume stream unavailable`. If it occurs naturally, observe whether v8 reports/retries it according to ownership and enabled-state policy.

## If STATUS still fails on v4.19.8

Do not immediately create v4.19.9.

Collect one bounded evidence bundle from the exact current tab:

- target count and exact URL;
- stop/generation selector counts;
- explicit assistant-role counts;
- `data-turn-key` and user-bubble counts;
- latest logical assistant-turn shape classification;
- current content protocol / guard version and script fingerprints;
- worker lifecycle/errors;
- conversation `lastControlAction`, `lastControlAt`, `lastStatus` before/after the marker;
- whether any `[LA_BRIDGE_FEEDBACK]` delivery was attempted.

Then classify the boundary before editing code:

```text
assistant turn selection/parsing
    -> content -> runtime sendMessage
    -> worker control validation
    -> state mutation
    -> feedback delivery
```

The long session repeatedly lost time by patching the wrong boundary before proving where the message stopped. Do not repeat that pattern.

## Release/verification evidence

The v4.19.8 release notes record:

- focused Bridge verification green;
- recovery helper tests 11/11;
- managed-session helper tests 13/13;
- PR #112 full five-job CI green;
- final candidate PR #113 full five-job CI green;
- production tag `v4.19.8` on final main.

A separate macOS control-admission smoke race was stabilized before final release. It was a test-harness timing problem: logs showed the unrelated task had actually received `TASK START` even when the old assertion timed out waiting for a later marker. Do not treat that historical CI issue as a Chat Bridge runtime defect.

## Continuation principle

The next conversation should act as an acceptance/diagnostic continuation, not restart design work from scratch.

Use current source and live evidence as truth. Old intermediate diagnoses are useful only when they explain a confirmed boundary above.
