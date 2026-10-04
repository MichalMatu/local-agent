# Conversation Fabric current plan

## Goal

Finish verification and live acceptance of the browser-native Conversation Fabric path in the operator's already authenticated primary Chrome session.

The separate-profile production approach is retired. PR `#141` introduced the native path. The same-browser repair passed live acceptance; see [the proof](SAME_BROWSER_PROOF_2026-10-04.md). Deployment of Local Agent itself must still be verified independently.

## Implemented production model

Production Conversation Fabric uses:

- one managed parent Superchat in the operator's normal Chrome;
- installed Chat Bridge `0.8.3` candidate;
- a dedicated trailing `LOCAL_AGENT_CF` control envelope, separate from legacy LAB controls;
- the existing `worker_spawn.js` `chrome.tabs` / `chrome.scripting` primitives;
- ordinary child tabs in the same authenticated Chrome session;
- `chrome.storage.local` campaign/dedupe state;
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

When a campaign is running, the existing minute GitHub-control alarm automatically collects stable results while the parent and Master are enabled. The parent waits for actual feedback. An explicit collect block is available for bounded observation recovery without resubmitting child prompts. GitHub-owned parent pacing still uses its exact `conversation_controls` record and monotonic generation.

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
- content protocol v18 / manifest 0.8.3 contract tests;
- real headless Chromium DOM smoke for parent control detection/composer feedback and child result capture/claim rejection;
- full repository CI coverage through the existing `bridge-browser`, test, coverage, Python 3.14 and macOS smoke jobs.

## Next work

The bounded two-child reasoning/transport milestone is complete. See the acceptance proof for captured results, cleanup and durable delivery receipts. Future substantive repository work requires fresh target context and canonical execution bindings; this proof did not execute repository mutations.

Keep the existing parent/Master enable guards, one active campaign per parent, global four-child capacity, bounded result/history storage and explicit interruption failures. Resume automation only for the intended user goal.

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
