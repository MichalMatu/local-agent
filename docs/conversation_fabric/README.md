# Conversation Fabric

Conversation Fabric is the reasoning-child layer beneath one managed Superchat parent. Current production design is browser-native: child work stays inside the operator's already authenticated primary Chrome session and installed Chat Bridge.

## Branch/state model

- `main` — production source of truth;
- `chat-bridge-state` — GitHub desired/runtime state for managed conversations;
- `operator-control` — durable Conversation Operator control/evidence where still applicable;
- `work/*` — disposable candidate branches only.

Historical isolated-profile/DEV-lab branches and dated checkpoint/self-diagnostic documents are evidence only, not current operating instructions.

## Architecture

```text
normal authenticated Chrome
  -> managed parent Superchat
  -> LOCAL_AGENT_CF delegate control
  -> Chat Bridge service worker
  -> existing worker_spawn.js ownership transaction
  -> reasoning-only child tabs in same Chrome session
  -> bounded stable child results
  -> durable campaign state
  -> exact owned child-tab cleanup
  -> terminal parent feedback at most once
  -> parent synthesis
  -> exact target .agent/tasks only if machine execution is justified
```

GitHub owns managed-chat pacing through `conversation_controls`. Local Agent remains the only machine executor. Children never receive repository mutation or machine execution authority.

## Current implementation

Chat Bridge `0.8.3` implements the primary-Chrome path directly:

- `conversation_fabric_protocol.js` — exact delegate/collect envelope and bounds;
- `conversation_fabric_content.js` — managed parent DOM controller and idempotent parent feedback;
- `worker_conversation_fabric.js` — campaign admission, dedupe, child lifecycle and stable collection;
- Conversation Fabric recovery/delivery guard modules — restart reconciliation and terminal at-most-once semantics;
- `worker_spawn.js` — transaction-safe tab creation/bootstrap/reconciliation primitives;
- `worker_spawn_result.js` + `spawn_result_content.js` — exact owned child result/cleanup helpers;
- durable campaign/result state in `chrome.storage.local`;
- content protocol `18`, Bridge manifest `0.8.3`;
- focused Node coverage plus real-extension/headless Chromium browser coverage.

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

Only the exact managed parent may issue these controls. Children cannot recursively delegate. Normal campaign observation is worker-driven by the existing GitHub-control alarm while parent + Master are enabled. Explicit `collect` is recovery/inspection for already-submitted children; it must never replay their bootstrap prompts.

## Durable lifecycle

- Each child spawn has an exact transaction id, child-request digest and bootstrap digest.
- Ambiguous/pre-submit submission fails closed instead of blindly replaying a child prompt.
- Stable results require the completion marker plus repeated identical observation.
- Every stable child result is stored in `chrome.storage.local` before sibling completion or tab cleanup.
- Transient observation failures remain pending/recoverable.
- Service-worker/session restart may lose transient tab ownership, but reattachment is allowed only when the page proves the exact transaction/request/bootstrap/current-child-URL claim. Reused tab id alone is never ownership proof.
- Cleanup closes only exact owned child tabs.

## Terminal delivery

Terminal feedback uses a durable campaign-specific delivery claim persisted before crossing the parent Send boundary.

- definite no-send clears the claim;
- confirmed send marks feedback delivered;
- an ambiguous claim surviving worker restart is treated as consumed and is not resent.

This is deliberate at-most-once behavior: replay safety is preferred over guaranteeing a second terminal notification after an ambiguous crash.

A parent cannot start a different new delegation while an older terminal campaign still has undelivered feedback. This prevents stale cross-campaign terminal replay.

## Execution authority

Conversation Fabric never supplies repository execution authority. If parent synthesis justifies machine work, the parent resolves the actual target through the canonical runtime catalog, requires `execution_enabled=true`, and uses the exact canonical target `agent_binding`.

The current catalog enables `local-agent`; self-execution still uses the same admission, binding, lease, resource and emergency-control rules as every other enabled target.

## Read order

1. `../CURRENT_HANDOFF.md`
2. `../GOLDEN_STANDARD.md`
3. `../AUTONOMOUS_CHAT_LOOP.md`
4. `../GITHUB_BRIDGE_CONTROL.md`
5. `CURRENT_PLAN.md`
6. `NEXT_CHAT_PROMPT.md`
7. `../OPERATIONS.md`

Historical checkpoint/self-diagnostic/DEV-lab/isolated-profile material remains evidence only.
