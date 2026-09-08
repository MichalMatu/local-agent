# Local Agent 4.18.18

## Summary

Fix the live Chat Bridge 0.5.6 diagnostic-feedback submit regression discovered during post-deploy validation of 4.18.17. Bridge could detect `[LAB:HELP]`, generate `[LA_BRIDGE_FEEDBACK]`, and insert it into the ChatGPT composer, but the final submit path could fail to activate the live Send control, leaving the operator to press Send manually.

## Live regression that triggered this release

Local Agent 4.18.17 / Chat Bridge 0.5.6 deployed successfully through natural self-update and the new LAB feedback loop was validated live with `[LAB:DEBUG]`: extension version 0.5.6, expected/reported protocol v5, exact `local-agent` binding, and remote runtime all matched. The next live `[LAB:HELP]` command was detected and its feedback text appeared in the composer, but the Bridge did not submit it. The operator manually pressed Send.

This isolates the defect to the final browser submit step rather than command parsing, worker diagnostics, binding, feedback generation, or composer insertion.

## Chat Bridge 0.5.7

- Advance content protocol from v5 to **v6** so already-open 0.5.6/v5 tabs are detectably stale and automatically receive the submit-path fix after the unpacked extension is reloaded.
- Make the live ChatGPT Send button's DOM `click()` path the primary submission mechanism. This follows the same control path as the operator's successful manual Send action and allows React button handlers to run.
- Stop preferring `form.requestSubmit(sendButton)`, which may bypass or fail to reproduce application-specific button behavior.
- Re-resolve the current enabled Send button immediately before submission. React may replace the button node while reconciling composer state; Bridge no longer trusts a button reference captured earlier in the delivery lifecycle.
- Retain `form.requestSubmit()` only as a last-resort fallback when no usable live button remains.
- Preserve exact-conversation, exact-composer, operator-edit, assistant-generation and delivery-authorization guards before submission.
- Preserve non-blocking `delivery_unconfirmed` semantics and exact retained-prompt recovery; this release does not introduce blind Enter simulation or repeated unbounded submit attempts.

## Regression coverage

- Add `submit_path_contract.test.js` requiring the live Send button click path, pre-submit button re-resolution, and forbidding regression to `requestSubmit(button)` as the preferred route.
- Existing isolated Chromium extension smoke continues to exercise confirmed submission, composer replacement, draft preservation, SPA navigation protection, overlap suppression, retained/unconfirmed prompts, LAB operator replay protection and service-worker restart behavior.
- Shared protocol tests continue to enforce one `CONTENT_PROTOCOL_VERSION` source of truth rather than duplicating the current numeric version across worker/content/popup/test harness files.

## Compatibility

- Executor/task schema, repository bindings, resource semantics, parallel scheduling, cancellation, self-update and LAB command privilege model are unchanged.
- Existing LAB HELP/DEBUG/SETTINGS/CHATS/OP commands are unchanged.
- Chat Bridge extension version advances from 0.5.6 to **0.5.7** and content protocol advances from v5 to **v6** only so deployed 0.5.6 tabs can be refreshed deterministically.

## Production boundary

At candidate preparation time, the deployed production release is Local Agent **4.18.17** at merge SHA `274166bcf907fc3c079d2372102defb5b81afa92`, installed through natural self-update. Production status subsequently reported 4.18.17, `self_revision=274166bcf907fc3c079d2372102defb5b81afa92`, shared supervisor PID `77070`, idle state, and no active task across LiteGraph, Tracker, Growbox and MatrixHub.

4.18.18 must not be tagged/frozen until exact-head CI, Chromium, macOS ARM64 and a live `[LAB:HELP]` feedback auto-submit test all pass. The live test must reload only the unpacked extension, leave the ChatGPT tab unreloaded, prove v5 -> v6 replacement, and confirm Bridge submits `[LA_BRIDGE_FEEDBACK]` without operator interaction.
