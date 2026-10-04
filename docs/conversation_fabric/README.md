# Conversation Fabric

Conversation Fabric is the reasoning-child layer beneath one managed Superchat parent. Current production design is browser-native: child work stays inside the operator's already authenticated primary Chrome session and installed Chat Bridge.

## Branch/state model

- `main` — production source of truth;
- `chat-bridge-state` — GitHub desired/runtime state for managed conversations;
- `operator-control` — durable Conversation Operator control/evidence where still applicable;
- `work/*` — disposable candidate branches only.

Historical isolated-profile/DEV-lab branches and documents are not current operating instructions.

## Architecture

```text
normal authenticated Chrome
  -> managed parent Superchat
  -> LOCAL_AGENT_CF control
  -> Chat Bridge service worker
  -> existing worker_spawn.js
  -> reasoning-only child tabs in same Chrome session
  -> bounded stable child results
  -> owned child-tab cleanup
  -> parent synthesis
  -> exact target .agent/tasks only if execution is justified
```

GitHub owns managed-chat pacing through `conversation_controls`. Local Agent remains the only machine executor. Children never receive machine execution authority.

## Current implementation

The Chat Bridge `0.8.2` candidate implements the primary-Chrome path directly:

- `conversation_fabric_protocol.js` — exact delegate/collect envelope and bounds;
- `conversation_fabric_content.js` — managed parent DOM controller and idempotent parent feedback;
- `worker_conversation_fabric.js` — campaign admission, dedupe, child lifecycle and stable collection;
- `worker_spawn.js` — existing transaction-safe tab creation/bootstrap/reconciliation primitives;
- `worker_spawn_result.js` + `spawn_result_content.js` — exact owned child result/cleanup helpers;
- browser-session campaign state in `chrome.storage.session`;
- content protocol `14`, Bridge manifest `0.8.2`;
- synthetic Node and real headless Chromium DOM coverage.

No production CDP attachment, dedicated browser/profile, Native Messaging, second scheduler or Local Agent-to-browser RPC is part of this design.

## Control model

Delegate:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"delegate","children":[...]}
LOCAL_AGENT_CF>>>
```

Collect:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"collect","campaign_id":"cf-..."}
LOCAL_AGENT_CF>>>
```

Only the exact managed parent may issue these controls. Normal Conversation Fabric pacing is GitHub-managed; LAB schedule markers are not used for child campaign continuation.

## Read order

1. `../CURRENT_HANDOFF.md`
2. `CURRENT_PLAN.md`
3. `NEXT_CHAT_PROMPT.md`
4. `../GOLDEN_STANDARD.md`
5. `../OPERATIONS.md`

Historical checkpoint/self-diagnostic/DEV-lab/isolated-profile material remains evidence only.
