# Local Agent 4.19.2

## Summary

Local Agent 4.19.2 fixes a Chat Bridge recovery gap in `Run now` and worker-owned content activation. After an unpacked extension/service-worker reload, an already-open ChatGPT tab could retain a same-version `__localAgentChatBridgeState` object after its old extension context was no longer usable. Automatic reinjection then loaded `content.js`, which correctly saw the retained protocol-v7 state and returned early, leaving no fresh message receiver. A manual `LAB:RELOAD=CONTENT` already performed the stronger reset, so automatic and explicit recovery had diverged.

The 4.19.2 candidate centralizes stale-content recovery in the worker. Content unavailability or protocol mismatch now disposes and clears the retained Bridge and exhaustion-guard globals before reinjecting the complete ordered content bundle and probing readiness again. A stale exhaustion guard with otherwise healthy content remains a narrower guard-only refresh so current content is not needlessly replaced.

## Chat Bridge 0.5.12

Chat Bridge advances from 0.5.11 to 0.5.12. Ordinary content protocol remains v7 and assistant timeout/exhaustion guard protocol remains v3; this release changes service-worker recovery semantics rather than the normal content wire contract.

Key changes:

- `Run now`, scheduled wake activation and worker-start content refresh share one hard stale-content reload owner in `worker_transport.js`.
- Hard content recovery disposes and clears both retained page globals, then injects `control_protocol.js`, `content_retry.js`, `content.js`, `dom_contract.js` and `exhaustion_guard.js` in dependency order.
- Guard-only failure keeps healthy content intact and refreshes only the exhaustion guard dependency set.
- `LAB:RELOAD=CONTENT` reuses the same centralized hard reload instead of maintaining a second scripting implementation.
- Source-contract and race tests now model one hard reload as the explicit reset-plus-bundle pair rather than depending on the previous single-injection implementation detail.
- A dedicated regression test proves `bridge:run-now` reaches `sent` only after stale page state is reset and the full content bundle is restored.
- The isolated real Chromium extension profile now reproduces the exact same-version stale-receiver state by disposing the live Bridge while retaining its global object; `Run now` must recover automatically and submit exactly one wake.

## Verification

Before the release metadata bump, candidate head `64a6b3aa8e66e1d70b60b56977f6b7afde1e5d52` passed the complete pull-request matrix:

- compile and Ruff;
- the full Chat Bridge Node contract/regression suite;
- Python unit/integration tests;
- coverage;
- Python 3.14 compatibility;
- isolated real-extension Chromium browser smoke including the new stale-content recovery scenario;
- macOS smoke covering process, checkpoint, multi-repository, binding, emergency-control and MCP paths.

Final release verification must pass again on the exact 4.19.2 metadata candidate before `main` advances.

## Compatibility and rollback

Task schema, repository hard binding, planner scope, scheduler/resource semantics, MCP behavior and daemon execution are unchanged by this fix. Content protocol remains v7, so already-open current-protocol tabs are recoverable without a normal manual page reload when Chrome still permits worker scripting into the tab.

The immediate released rollback baseline is `v4.19.1`, tagged at commit `4cb19ec998acdf48462021c2821f488095e69442`.

After deploying the extension update, reload the unpacked extension card in `chrome://extensions`. The first subsequent worker activation or `Run now` may repair stale page state automatically; a normal ChatGPT page reload should not be required for this recovered same-version receiver case.
