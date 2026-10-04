# Conversation Fabric current plan

## Goal

Finish verification and live acceptance of the browser-native Conversation Fabric path in the operator's already authenticated primary Chrome session.

The separate-profile production approach is retired. The implementation is now in PR `#141`; the remaining work is verification, merge/deploy/reload and one bounded real live proof.

## Implemented production model

Production Conversation Fabric uses:

- one managed parent Superchat in the operator's normal Chrome;
- installed Chat Bridge `0.8.2` candidate;
- a dedicated trailing `LOCAL_AGENT_CF` control envelope, separate from legacy LAB controls;
- the existing `worker_spawn.js` `chrome.tabs` / `chrome.scripting` primitives;
- ordinary child tabs in the same authenticated Chrome session;
- `chrome.storage.session` campaign/dedupe state;
- exact transaction/tab/request/bootstrap ownership;
- bounded stable child-result capture and exact owned-tab cleanup;
- GitHub `conversation_controls` for pacing/next wakes.

Production does **not** launch another browser, create/migrate another ChatGPT profile, copy cookies, use CDP as a second production control plane, add Native Messaging, create a Local Agent-to-browser RPC, or use LAB scheduling for normal Conversation Fabric pacing.

## Candidate mechanics

A parent delegation ends with:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"delegate","children":[
  {"id":"audit","role":"research","prompt":"..."},
  {"id":"verify","role":"verification","prompt":"..."}
]}
LOCAL_AGENT_CF>>>
```

The Bridge admits this only from the exact top-frame managed parent. Each child bootstrap states that it is reasoning-only and may not create Local Agent tasks, run machine commands, mutate repositories or make the final parent decision.

When a campaign is running, Bridge returns a parent feedback prompt containing the exact collect block and instructions to schedule one GitHub-managed wake. The parent updates its exact `conversation_controls` record with `control_generation += 1` and a bounded `next_wake_at`.

Collection ends with:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"collect","campaign_id":"cf-..."}
LOCAL_AGENT_CF>>>
```

Results must be stable across repeated observations before they are returned to the parent. Completed campaigns close only their owned child tabs.

## Verification already encoded

The candidate includes:

- exact positive/negative protocol tests;
- worker lifecycle tests for two children, dedupe, managed-parent admission, stable collect and partial-failure cleanup;
- content protocol v14 / manifest 0.8.2 contract tests;
- real headless Chromium DOM smoke for parent control detection/composer feedback and child result capture/claim rejection;
- full repository CI coverage through the existing `bridge-browser`, test, coverage, Python 3.14 and macOS smoke jobs.

## Remaining sequence

1. Freeze one final candidate SHA with code + current docs/release metadata.
2. Require exact-head full CI green on that SHA.
3. Inspect PR `#141` reviews/threads and merge only with no blocking review.
4. Verify current `main`, Local Agent runtime `self_revision`, and installed Chat Bridge source/version.
5. Reload the unpacked Chat Bridge in the operator's normal Chrome session so content protocol v14/Bridge 0.8.2 is active in the existing parent tab.
6. Run one bounded live acceptance with at least two narrow non-overlapping reasoning children.
7. Verify children appear as ordinary tabs in the same Chrome session and no extra login/Cloudflare/profile is involved.
8. Use only GitHub-managed `conversation_controls` for bounded collect wakes.
9. Collect both stable results, verify exact owned-tab cleanup, and let the parent synthesize the final answer.
10. If execution is justified, publish at most one exact target-repository task with canonical binding and stable dedupe key; otherwise publish no executable task.
11. Verify no duplicate execution and leave the parent in the intended paused state.

## Stop conditions

Stop rather than weakening safety if:

- the parent is not a managed exact conversation/tab;
- child tab/transaction ownership is ambiguous;
- a child obtains machine execution authority;
- result identity is missing/unstable beyond bounded retry;
- GitHub conversation-control ownership/generation is uncertain;
- target binding/repository identity is uncertain;
- equivalent expensive tasks execute twice.

A missing isolated profile, isolated-profile login failure or Cloudflare challenge is not a production blocker because that path is no longer part of the accepted architecture.

## Success criteria

The milestone passes only when the user can visibly see one managed parent orchestrating at least two reasoning-only child tabs inside the already-running normal Chrome session, collecting their stable results, closing those owned tabs and—only if justified—causing no more than one deterministic target-bound Local Agent execution.
