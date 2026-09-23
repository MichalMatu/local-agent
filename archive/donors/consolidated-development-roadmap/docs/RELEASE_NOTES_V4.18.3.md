# Local Agent 4.18.3 / Chat Bridge 0.5.2

This release freezes the post-4.18.2 Chat Bridge corrections after code audit, full CI and live operator control validation. Python executor semantics, task contracts, hard binding and the standalone-C6 retirement remain unchanged.

## Chat Bridge finalization

- Remove the durable ambiguous-delivery blocker introduced in 4.18.1. A lost post-submit confirmation is now diagnostic-only `delivery_unconfirmed`; it never creates `pendingDelivery`, auto-pauses a conversation, blocks controls or requires manual ✓/× recovery.
- Preserve exact URL/binding/content-protocol checks, composer mutation protection, pre-submit authorization and one in-memory overlap guard while a delivery is active.
- Split the service worker into focused ownership modules for state, runtime, binding, scheduling, transport, controls, delivery, conversation/operator mutations and event routing. `service_worker.js` is composition only.
- Make the global Bridge **Master** switch strictly operator-only. Assistant controls may overwrite ordinary per-conversation enabled/paused state, next wake and interval, but cannot change Master.
- Preserve per-chat desired timing while Master is off so re-enabling Master reconciles scheduling without assistant authority over the global gate.
- Add `popup_live.js` as a separate UI synchronization module. While the popup is open it reacts to storage changes and polls bounded state every 500 ms, patching cards in place without overwriting a focused interval edit.

## Live validation

The installed unpacked extension was reloaded and exercised against the bound `local-agent` conversation. Live controls were observed to work for repeated `RESUME`, `STOP`, `PAUSE`, `NEXT=30s` and `INTERVAL=1m`. The open popup reflected externally applied state changes without being closed/reopened. A small visual delay remains consistent with the bounded live-sync cadence and does not affect control application.

The global Master switch remained outside assistant control throughout the sequence.

## Architecture audit

The repository still satisfies its intended decomposition:

- all reusable Python implementation lives under `local_agent/`;
- the four root Python launchers remain tiny operational entrypoints and are enforced by `tests/test_package_layout.py`;
- Chat Bridge worker responsibilities remain split by ownership rather than accumulating in a replacement god object;
- live popup synchronization is isolated from the main popup action/rendering module;
- the only audit defect found before freeze was stale `docs/ARCHITECTURE.md` text describing the removed durable delivery journal and monolithic worker ownership; this release corrects that documentation.

`popup.js` remains the largest Bridge UI source because it owns the explicit popup rendering and operator actions, but the newly changing background synchronization concern is already extracted. No further cosmetic split is required for this freeze.

## Release hygiene

The release version is `4.18.3`. After the exact release commit is green, tag that commit `v4.18.3` and remove obsolete merged/temporary development branches. Keep the operational `main`, `chat-bridge-state` and `operator-control` branches.

Standalone `esp32-c6-zigbee` remains retired from the active catalog/workspace/config/tests/docs. Historical release notes may mention its former identity only as history; this release does not restore it.
