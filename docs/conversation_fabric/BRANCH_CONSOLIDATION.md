# Branch consolidation record

Status: complete.

Canonical development branch: `develop/conversation-fabric`.

Production/runtime branches remain separate: `main`, `chat-bridge-state`, `operator-control`.

## Consolidated lineage

The development branch is linearly ahead of production; it is not a merge of diverged histories.

- production base: `main@474000b5d4b015958fe92be491968dc4625b4a84`;
- latest inherited transient-recovery checkpoint: `fc4cb25da4c779daff87e93dedaa906363e3b49e`;
- unified core transplant: `596ee76a60e701d603b1b969843984976620e84a`;
- donor snapshot/history consolidation: `fdf5d099df39788655f5b41325b8e769fc668981`;
- complete active Execution Fabric test transplant: `45aebf2f9a561e862def4d239548cf062ac605e0`;
- first consolidation record: `84cf5cf250cbe9505823bea3d6de68a64f07efa1`.

## Active assets preserved

- latest Chat Bridge transient assistant recovery implementation and tests;
- verified `local_agent/workflow/` Execution Fabric core;
- workflow CLI, shared control-Git lock, workflow fixtures and full regression corpus;
- durable result-event outbox;
- notification-only Chrome Native Messaging host/installer + tests;
- pure `chat_bridge/event_wake_state.js` model + tests;
- Conversation Fabric current architecture and historical design evidence.

Execution Fabric remains intentionally unwired from production runtime entrypoints. The pure Event Wake model is intentionally not imported by `chat_bridge/service_worker.js` yet.

## Deliberately not transplanted as active runtime

Old Event Wake copies of central Chat Bridge worker/content/delivery files were not made authoritative because they predate the later transient/timeout recovery line. Their behavior may be selectively reimplemented against current owners only when covered by current recovery tests.

No automatic workflow scheduler, production `SPAWN_CHILD`, child-registration authority, or broader Native Messaging command channel has been enabled.

## Donor history

Before deleting the former development branches, exact donor trees were committed under `archive/donors/` in historical commit:

`fdf5d099df39788655f5b41325b8e769fc668981`

Those duplicated trees are intentionally removed again from the current HEAD to keep code search, diffs and agent context clean. They remain reachable through Git history and do not need to live in the active working tree.

Former development branches deleted as superseded:

- `feature/chat-bridge-event-wake`;
- `feature/openworker-governance`;
- `feature/conversation-fabric-superchat`;
- `plan/consolidated-development-roadmap`;
- `work/chat-bridge-live-chat-states`;
- `maintenance/transient-recovery-patch`;
- `work/transient-recovery-validation`.

Draft PRs #77, #81 and #85 were closed without merge as superseded.

## Validation

The consolidated HEAD `84cf5cf250cbe9505823bea3d6de68a64f07efa1` passed the full CI matrix before this documentation/tree hygiene cleanup: unit/integration, coverage, Python 3.14, macOS smoke and Chromium/Bridge smoke.

Every subsequent cleanup commit must pass the same exact-head CI before becoming the new trusted development baseline.
