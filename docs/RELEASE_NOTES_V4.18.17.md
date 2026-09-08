# Local Agent 4.18.17

## Summary

Fix the live Chat Bridge 0.5.5 popup/content-protocol regression discovered immediately after deploying 4.18.16, centralize content activation/version ownership, and add a bounded future-proof LAB diagnostic/operator command plane so Bridge can diagnose itself from the bound ChatGPT conversation.

## Live regression that triggered this release

Local Agent 4.18.16 / Chat Bridge 0.5.5 deployed successfully and the Local Agent executor passed live self-update and cross-repository parallel smoke. During the intended stale-tab Bridge validation, the operator reloaded the unpacked extension but deliberately did not reload the ChatGPT tab. `Add current chat` failed with:

```text
Error: This ChatGPT tab has an older Bridge content script. Reload the tab, then try again.
```

Root cause: `worker_transport.js` and `content.js` were upgraded to content protocol v4, but `popup.js` still hard-coded protocol v3 and retained a second, older reinjection policy that deliberately rejected a reachable mismatched content script. A hard browser refresh did not address the architectural mismatch.

## Chat Bridge 0.5.6

- Keep content protocol v4 but move `CONTENT_PROTOCOL_VERSION` to the single shared `control_protocol.js` source of truth.
- Remove popup-owned protocol versioning and popup-owned `chrome.scripting.executeScript` logic.
- Route popup `Add current chat` activation through the service worker with `bridge:ensure-tab-content`.
- The worker now performs one centralized force-refresh path: dispose existing Bridge/guard listeners, inject `control_protocol.js`, `content_retry.js`, `content.js`, `dom_contract.js`, and `exhaustion_guard.js`, then probe content protocol and guard readiness again.
- Add a regression contract that forbids duplicate `CONTENT_PROTOCOL_VERSION` declarations in content, worker, popup and test harness.
- Add a direct worker regression for the exact live failure: reachable protocol 3 -> worker force refresh -> protocol 4 ready, without a ChatGPT page reload.

## Future-proof LAB command plane

The protocol now exposes a formal command catalog with explicit privilege/category metadata instead of accumulating undocumented ad-hoc markers.

Assistant-safe read/diagnostic commands:

```text
[LAB:HELP]
[LAB:CAPABILITIES]
[LAB:STATUS]
[LAB:DEBUG]
[LAB:SETTINGS]
[LAB:CHATS]
[LAB:CHAT=<chat-id>]
```

Bridge-local maintenance commands:

```text
[LAB:RELOAD=CONTENT]
[LAB:RELOAD=BRIDGE]
[LAB:RESTART=WORKER]
```

Existing pacing controls remain supported:

```text
[LAB:PAUSE]
[LAB:RESUME]
[LAB:STOP]
[LAB:NEXT=<duration>]
[LAB:INTERVAL=<minutes|AUTO>]
```

Operator mutation commands must originate from a user-authored ChatGPT message and therefore use a distinct namespace:

```text
[LAB:OP:ADD=<repository-id>]
[LAB:OP:REMOVE]
[LAB:OP:ENABLE]
[LAB:OP:DISABLE]
[LAB:OP:INTERVAL=<minutes|AUTO>]
[LAB:OP:RELOAD=CONTENT]
[LAB:OP:RELOAD=BRIDGE]
```

The assistant parser rejects `LAB:OP:*`. The operator scanner reads only DOM messages with `data-message-author-role="user"`. Worker-side validation still requires the same extension id, top frame and exact normalized ChatGPT conversation URL.

## Diagnostic feedback loop

- `HELP`, `CAPABILITIES`, `STATUS`, `DEBUG`, `SETTINGS`, `CHATS` and `CHAT=<id>` return `[LA_BRIDGE_FEEDBACK]` evidence into the same ChatGPT conversation as a Bridge-generated user message.
- `DEBUG` reports extension version, expected/reported content protocol, exact tab/url, whether the chat is configured, current conversation state/schedule, Master state and runtime source/pacing.
- `HELP` returns the live command catalog, so a conversation can discover the capabilities of its installed Bridge version rather than relying on stale model context.
- `CHATS`/cross-chat inspection is global only for the `local-agent` infrastructure binding. Ordinary project-bound conversations receive current-chat-only routing metadata and cannot use diagnostics to inspect other project bindings.
- Diagnostic feedback is explicitly read-only evidence and is not operator approval or permission to change repository binding.

## Operator chat management from the conversation

- `OP:ADD=<repository-id>` can bind the current previously unconfigured chat to one exact runtime-catalog repository; the new chat is added disabled, matching conservative popup onboarding semantics.
- `OP:REMOVE`, `OP:ENABLE`, `OP:DISABLE` and `OP:INTERVAL` operate only on the exact current chat.
- Operator command dedupe is persistent and bounded independently from conversation state, so ADD can dedupe before/after binding and REMOVE remains deduped after the conversation record is deleted.
- The dedupe cache retains at most 64 recent chat fingerprints.
- Assistant messages cannot execute the operator namespace, preserving the hard-binding rule that repository selection is an operator action.

## Explicit non-capabilities

This release does not silently grant the browser extension repository-write or Local Agent supervisor authority.

`CAPABILITIES` reports these as unavailable through Bridge:

- repository task cancellation via direct Bridge transport;
- Local Agent supervisor restart via direct Bridge transport.

The ChatGPT planner may still use existing repository-scoped `cancel_task` through the established Git-backed Local Agent control plane when exact task evidence justifies cancellation. A future direct Bridge cancel/restart command requires a separate trusted transport and is not implied by this LAB namespace.

## Compatibility

- Task schema, binding UUIDs, repository registry, executor resource semantics, result schema, parallel scheduler, BUG-002 behavior and Local Agent self-update semantics are unchanged.
- Existing Bridge schema-v3 conversation state remains valid.
- Existing STOP/PAUSE/RESUME/NEXT/INTERVAL markers remain compatible.
- Content protocol remains v4; Chat Bridge extension version advances from 0.5.5 to 0.5.6.

## Verification required before merge

The final 4.18.17 candidate must pass:

- Node syntax and all Chat Bridge unit/contract tests;
- the exact popup protocol-3 -> protocol-4 worker recovery regression;
- assistant/operator privilege-separation tests;
- full Python unit/integration suite and coverage;
- Python 3.14 compatibility;
- macOS ARM64 smoke;
- isolated Chromium extension smoke;
- live stale-tab validation after extension Reload with no ChatGPT page reload.

## Production state

While this file is on the candidate branch, the current production Local Agent release is 4.18.16 at merge SHA `f33c4d4d7e2e0b89e9fe5ec1dec39cc8a8bc47ef`. Production self-update to 4.18.16 was confirmed and a hardware-free LiteGraph/Tracker live parallel smoke completed successfully. Chat Bridge 0.5.5 is deployed but the popup stale-content onboarding regression above prevents treating 4.18.16 as the final Bridge freeze point.

## Rollback

The last tagged frozen release remains `v4.18.15` at `338dd59e16e2c52c8148625e4f7bd2551aab92e8`, with `rollback/v4.18.15-production-validated` preserving the earlier exact runtime-validation point. A new 4.18.17 rollback/tag point must be created only after final merge and live Bridge validation.
