# Current handoff — browser-native Conversation Fabric

Date: 2026-10-04

Status: Local Agent remains on release line `v4.20.6`. The current candidate advances Chat Bridge from `0.8.1` to `0.8.3` and implements Conversation Fabric child delegation inside the operator's already authenticated primary Chrome session. The old isolated-profile/Playwright production assumption is retired.

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
- current candidate Bridge: `0.8.3`;
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

Isolation is logical: exact parent conversation, tab id, child URL, spawn transaction, request/bootstrap digests and durable local campaign state. Ambiguous ownership fails closed.

## Implemented candidate

Merged PR `#141` introduced the native path. The verified same-browser repair completes it:

- `conversation_fabric_protocol.js` defines a dedicated non-LAB `LOCAL_AGENT_CF` control envelope;
- only a managed parent tab may start or collect a campaign;
- `worker_conversation_fabric.js` reuses the existing `worker_spawn.js` `chrome.tabs` / `chrome.scripting` primitives;
- campaign/dedupe state is durable in `chrome.storage.local`;
- children receive an explicit reasoning-only contract with no machine/task authority;
- `spawn_result_content.js` captures bounded stable assistant results from the exact owned child tab;
- completed/failed campaigns close only their owned child tabs;
- the existing minute GitHub-control alarm automatically collects and delivers results; GitHub `conversation_controls` remains authoritative for remotely managed parent pacing;
- content protocol advances to `18`, Bridge manifest to `0.8.3`;
- focused Node tests plus a real headless Chromium parent/child DOM smoke cover the new boundary.

No Native Messaging path, Local Agent-to-browser RPC, new scheduler or second browser is introduced.

## Current milestone

The same-browser repair passed full verification, macOS smoke, the real-extension browser/DOM suite and a live two-child acceptance in the normal Chrome session. See [the acceptance proof](conversation_fabric/SAME_BROWSER_PROOF_2026-10-04.md) for exact evidence and scope. The parent was paused after completion. Repository mutation was not required or claimed by the arithmetic transport proof.

For future work, verify fresh source/runtime identity and the installed Bridge version. Children receive bounded source context explicitly; the parent synthesizes results and owns any exact target-bound executable task. No automatic replay is permitted after interrupted spawning.
