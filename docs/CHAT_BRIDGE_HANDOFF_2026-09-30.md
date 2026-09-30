# Chat Bridge 0.6.0 fresh-context audit handoff — 2026-09-30

## Purpose

Start the next session from a clean context and audit the **new GitHub-backed Chat Bridge architecture itself**, not the old assistant-DOM schedule parser incident.

Do not assume the 0.6.0 design is optimal merely because the live E2E passed. Treat the release as a working baseline and look for simplification, failure-mode gaps, stale compatibility code, observability problems and opportunities to reduce browser/DOM coupling further.

## Release baseline

Prepared release:

```text
Local Agent:      4.19.9
Chat Bridge:      0.6.0
content protocol: 13
assistant guard:  8
runtime schema:    3 + optional conversation_controls
```

Primary implementation branch before merge: `feature/github-bridge-control`.

Canonical docs after release:

- `docs/GITHUB_BRIDGE_CONTROL.md`
- `docs/AUTONOMOUS_CHAT_LOOP.md`
- `chat_bridge/README.md`
- `docs/CHATGPT_DOM_CONTRACT.md`
- `docs/GOLDEN_STANDARD.md`
- `docs/RELEASE_NOTES_V4.19.9.md`

## Why the architecture changed

The previous schedule-control path depended on assistant text markers such as `[LAB:STATUS]`, `[LAB:NEXT=2m]` and `[LAB:PAUSE]` being found in the rendered ChatGPT transcript.

A saved failing page proved the renderer could attach `data-conversation-role="assistant"` only to an accessibility heading containing `ChatGPT said:` while the real assistant body was a sibling. Earlier releases had also accumulated grouped-turn fallbacks and ordering fixes.

The actual scheduling task is simple and should not depend on reconstructing assistant-message semantics from a changing web UI. 0.6.0 therefore makes GitHub desired state authoritative.

## Current architecture

```text
ChatGPT planner
    |
    | GitHub connector read/write
    v
chat-bridge-state/chat_bridge/runtime.json
    |
    | public fetch
    v
Chat Bridge MV3 worker
    |
    | reconcile exact desired state
    v
chrome.alarms
    |
    v
exact ChatGPT tab/conversation
    |
    | content script composer + Send
    v
planner wake
```

Managed schedule operations are `STATUS`, `PAUSE`, `RESUME`, `NEXT`, `INTERVAL` through `conversation_controls`.

Every mutation increments `control_generation`. Binding/repository/revision mismatch fails closed. Applied state is scoped to binding revision, control generation and local conversation generation.

The extension contains no GitHub credential and never writes GitHub state.

## Key source files

Read these first:

```text
chat_bridge/github_control_model.js
chat_bridge/worker_github_control.js
chat_bridge/worker_github_legacy_gate.js
chat_bridge/worker_runtime.js
chat_bridge/worker_schedule.js
chat_bridge/worker_binding.js
chat_bridge/worker_events.js
chat_bridge/service_worker.js
chat_bridge/content.js
chat_bridge/bridge_state.js
```

Tests to understand before proposing changes:

```text
chat_bridge/github_control_model.test.js
chat_bridge/github_control_worker.test.js
chat_bridge/bridge_protocol_contract.test.js
chat_bridge/service_worker.test.js
chat_bridge/service_worker_races.test.js
scripts/bridge_control_browser_cases.cjs
```

## Live proof completed

Canonical conversation:

```text
conversation: chat-e8ad8275
repository:   host-ops
binding:      16d688b6-b0ef-4905-a5bd-24e59c99cfb4
binding rev:  1
```

Daily Chrome, not the diagnostic CfT profile, completed:

1. generation 1: PAUSED (`enabled=false`);
2. generation 2: RESUME;
3. generation 3: exact two-minute NEXT;
4. Bridge discovered GitHub state and placed the wake in the correct composer;
5. one observed delivery attempt initially left the wake text in the composer without submission;
6. the subsequent attempt submitted normally and the expected wake arrived in this conversation;
7. generation 4: PAUSED (`enabled=false`, `next_wake_at=null`).

Final desired state must remain PAUSED unless the next session intentionally arms it.

That transient composer-without-submit observation is **not closed by assumption**. The successful retry proves the end-to-end path can work, but the fresh audit should decide whether the existing `waitForSendButton` / authorization / live-button re-resolution / click / confirmation path has a deterministic first-attempt gap.

## Candidate CI evidence

The exact pre-release 0.6.0 candidate `03861f590947e3bd34506db085a3b79b02196598` passed all five CI jobs:

- test (compile, lint, Bridge validation, full unittest);
- coverage;
- Python 3.14;
- real-extension browser smoke;
- macOS ARM64 smoke; the focused macOS suite reported 291 tests, `OK`.

Release metadata/doc changes must have their own exact-SHA green CI before merge/tag.

## What is intentionally legacy

For a GitHub-managed chat, assistant schedule markers and user OP pacing controls are recognized only as compatibility no-ops (`github_control_managed`).

Still outside the GitHub desired-state design:

- `ADD` / `REBIND` / `REMOVE` binding mutation;
- Bridge/content reload and worker maintenance;
- some inspection/diagnostic commands;
- local popup controls and global Master.

Do not automatically migrate these in the first audit. First decide whether each belongs in GitHub desired state, local operator UI, or should be deleted.

## Fresh-context audit questions

Audit from source, tests and current runtime evidence. At minimum answer:

1. Is `conversation_controls` the right ownership boundary or should desired/applied state be split into separate GitHub objects?
2. Do we need an applied-state ACK visible outside Chrome, and if so can it be published without putting GitHub credentials in the extension?
3. Is one-minute polling acceptable for latency/traffic, or should the design use a different wake/discovery mechanism?
4. Are `control_generation`, `bindingRevision` and `localGeneration` sufficient and minimal, or can races still replay/erase a one-shot wake?
5. What happens with two browser profiles running the same conversation and different local storage? Can duplicate wake delivery still occur?
6. Does global Master interact correctly with remote desired `enabled=true` and later re-enable?
7. Can a stale public runtime cache delay PAUSE or replay NEXT? Inspect cache invalidation and fetch semantics.
8. Is the legacy authority gate complete for every local/popup/LAB pacing mutation?
9. Can popup UX make GitHub ownership obvious instead of appearing to offer authoritative local pacing controls?
10. Can assistant-side schedule scanning/parsing now be deleted or moved behind an explicit legacy feature boundary?
11. Reproduce/analyze the observed first attempt that wrote the wake but did not submit. Add a regression only if the exact cause is demonstrated.
12. Review security: public desired state, exact binding checks, malicious/stale runtime records, timestamp bounds, duplicate controls and fail-closed behavior.
13. Review performance: MV3 wake frequency, fetch/cache behavior, storage writes and alarm churn.
14. Review maintainability: module ownership, duplicated state machines, test harness fidelity and documentation drift.

## Audit output expected

Do **not** immediately refactor everything. Produce in order:

1. architecture map from current `main`;
2. confirmed invariants and live assumptions;
3. prioritized findings (`critical/high/medium/cleanup`);
4. minimal recommended changes with explicit non-goals;
5. test plan including negative/race/browser cases;
6. only then implement fixes on a fresh branch.

Prefer deleting obsolete complexity over layering more heuristics.

## Operational cautions for the next session

- `local-agent` remains execution-disabled: inspect/edit it through direct GitHub operations, not a Local Agent task.
- Use `host-ops` only for actual Mac/browser/local commands.
- Do not launch local Codex.
- Do not revive assistant LAB schedule markers for normal managed pacing.
- Do not change the global Master from conversation desired state.
- Do not arm this conversation merely to inspect it; read GitHub status directly.
- If a live wake test is necessary, use a bounded generation sequence and finish PAUSED.

## Clean starting prompt

Use this in a new ChatGPT window after release/production cleanup:

> Przeanalizuj od zera `MichalMatu/local-agent` po release 4.19.9, skupiając się na Chat Bridge 0.6.0 i GitHub-backed `conversation_controls`. Najpierw przeczytaj `docs/CHAT_BRIDGE_HANDOFF_2026-09-30.md` oraz wskazane tam source/test files. Zrób niezależny audit architektury, race conditions, security, MV3 lifecycle, dwóch profili Chrome, cache/polling, popup ownership oraz wake submit path. Nie zakładaj, że obecny kod jest optymalny tylko dlatego, że E2E przeszedł. Najpierw findings i plan, potem poprawki na świeżej gałęzi. Nie wracaj do assistant LAB schedule transportu.
