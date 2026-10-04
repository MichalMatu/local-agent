# Current handoff — browser-native Conversation Fabric

Date: 2026-10-04

Status: Local Agent remains on release line `v4.20.6`. The current candidate advances Chat Bridge from `0.8.1` to `0.8.2` and implements Conversation Fabric child delegation inside the operator's already authenticated primary Chrome session. The old isolated-profile/Playwright production assumption is retired.

## Source of truth

Read fresh repository/runtime evidence in this order:

1. `AGENTS.md`
2. this file
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/conversation_fabric/CURRENT_PLAN.md`
6. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

Historical isolated-profile, DEV-lab, self-diagnostic and checkpoint documents are evidence only.

## Immutable baseline

- Local Agent release tag: `v4.20.6` -> `48eb9d8b6c26a9dfb317906d5099acabce8719c8`;
- Local Agent release line: `4.20.6`;
- released Bridge at that tag: `0.8.1`;
- current candidate Bridge: `0.8.2`;
- `local-agent` remains execution-disabled as a Local Agent task target;
- production `self_revision` must always be read fresh before live acceptance.

## Accepted production browser model

```text
normal authenticated Chrome
  -> managed parent Superchat tab
  -> installed Chat Bridge
  -> LOCAL_AGENT_CF control
  -> existing worker_spawn.js primitives
  -> ordinary reasoning-only child tabs in the same Chrome session
  -> stable child result capture
  -> owned-tab cleanup
  -> parent synthesis
  -> exact target .agent/tasks only when execution is justified
```

Production Conversation Fabric must not launch a second Chrome/Chromium process, maintain a separate ChatGPT profile, copy cookies, use CDP as a second browser-control plane, require another login, or treat Cloudflare recovery as normal orchestration.

Isolation is logical: exact parent conversation, tab id, child URL, spawn transaction, request/bootstrap digests and browser-session campaign state. Ambiguous ownership fails closed.

## Implemented candidate

PR `#141` now implements the pivot in Chat Bridge itself:

- `conversation_fabric_protocol.js` defines a dedicated non-LAB `LOCAL_AGENT_CF` control envelope;
- only a managed parent tab may start or collect a campaign;
- `worker_conversation_fabric.js` reuses the existing `worker_spawn.js` `chrome.tabs` / `chrome.scripting` primitives;
- campaign/dedupe state is browser-session scoped in `chrome.storage.session`;
- children receive an explicit reasoning-only contract with no machine/task authority;
- `spawn_result_content.js` captures bounded stable assistant results from the exact owned child tab;
- completed/failed campaigns close only their owned child tabs;
- parent continuation uses GitHub `conversation_controls` with incremented `control_generation`; normal Conversation Fabric pacing does not use LAB schedule markers;
- content protocol advances to `14`, Bridge manifest to `0.8.2`;
- focused Node tests plus a real headless Chromium parent/child DOM smoke cover the new boundary.

No Native Messaging path, Local Agent-to-browser RPC, new scheduler or second browser is introduced.

## Current milestone

Do not merge or live-prove from an unverified SHA. The remaining sequence is:

1. synchronize current docs/release metadata with the `0.8.2` candidate;
2. require exact-head full CI, including `bridge-browser` DOM smoke;
3. merge PR `#141` only if exact-head CI is green and no blocking review exists;
4. verify the installed/current source revision and reload the unpacked Chat Bridge in the normal Chrome session;
5. run one bounded live Superchat acceptance with at least two non-overlapping reasoning children;
6. collect both results, confirm owned tabs are retired, and let the parent make the final decision;
7. if execution is justified, queue at most one exact target-bound task and prove no duplicate execution.

The next live proof must use the user's normal Chrome session. A dedicated `chat-bridge-cft` profile or another isolated browser does not satisfy acceptance.
