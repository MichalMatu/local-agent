# Local Agent 4.18.18

## Summary

Fix the live Chat Bridge 0.5.6 diagnostic-feedback submit regression discovered during post-deploy validation of 4.18.17. Bridge could detect `[LAB:HELP]`, generate `[LA_BRIDGE_FEEDBACK]`, and insert it into the ChatGPT composer, but the final submit path could fail to activate the live Send control, leaving the operator to press Send manually.

## Live regression that triggered this release

Local Agent 4.18.17 / Chat Bridge 0.5.6 deployed successfully through natural self-update and the new LAB feedback loop was validated live with `[LAB:DEBUG]`: extension version 0.5.6, expected/reported protocol v5, exact `local-agent` binding, and remote runtime all matched. The next live `[LAB:HELP]` command was detected and its feedback text appeared in the composer, but the Bridge did not submit it. The operator manually pressed Send.

This isolates the original defect to the final browser submit step rather than command parsing, worker diagnostics, binding, feedback generation, or composer insertion.

## Chat Bridge 0.5.7

- Advance content protocol from v5 to **v6** so already-open 0.5.6/v5 tabs are detectably stale and can receive the submit-path fix without reloading the ChatGPT page.
- Make the live ChatGPT Send button's DOM `click()` path the primary submission mechanism. This follows the same control path as the operator's successful manual Send action and allows React button handlers to run.
- Stop preferring `form.requestSubmit(sendButton)`, which may bypass or fail to reproduce application-specific button behavior.
- Re-resolve the current enabled Send button immediately before submission. React may replace the button node while reconciling composer state; Bridge no longer trusts a button reference captured earlier in the delivery lifecycle.
- Treat the exact post-insertion composer DOM text as the protected Bridge-owned snapshot. Rich contenteditable editors may canonicalize whitespace/newlines while preserving the visible payload; any later operator edit still changes the snapshot and fails closed before submission.
- Retain `form.requestSubmit()` only as a last-resort fallback when no usable live button remains.
- On service-worker activation, probe configured open ChatGPT tabs and re-inject content only when it is unavailable or reports a protocol mismatch. This closes the unpacked-extension Reload gap without sending a wake, mutating a binding, or requiring a ChatGPT page reload.
- Preserve exact-conversation, operator-edit, assistant-generation and delivery-authorization guards before submission.
- Preserve non-blocking `delivery_unconfirmed` semantics and exact retained-prompt recovery; this release does not introduce blind Enter simulation or repeated unbounded submit attempts.

## Regression coverage

- Add `submit_path_contract.test.js` requiring the live Send button click path, pre-submit button re-resolution, and forbidding regression to `requestSubmit(button)` as the preferred route.
- Add `startup_content_refresh.test.js` requiring worker startup to refresh a stale configured tab, leave a current-protocol tab untouched, send zero wake/feedback prompts, and preserve conversation binding/schedule state.
- Add deterministic isolated Chromium coverage for the exact live regression: hold Send disabled until `[LA_BRIDGE_FEEDBACK] command=HELP` is present, then release Send and require Bridge to submit automatically with no operator action.
- Existing isolated Chromium smoke continues to exercise confirmed submission, composer replacement, draft preservation, SPA navigation protection, overlap suppression, retained/unconfirmed prompts, LAB operator replay protection and service-worker restart behavior.
- Shared protocol tests continue to enforce one `CONTENT_PROTOCOL_VERSION` source of truth rather than duplicating the current numeric version across worker/content/popup/test harness files.

## Compatibility

- Executor/task schema, repository bindings, resource semantics, parallel scheduling, cancellation, self-update and LAB command privilege model are unchanged.
- Existing LAB HELP/DEBUG/SETTINGS/CHATS/OP commands are unchanged.
- Chat Bridge extension version advances from 0.5.6 to **0.5.7** and content protocol advances from v5 to **v6** so deployed 0.5.6 tabs can be refreshed deterministically.
- Service-worker activation refresh is transport-only. It does not perform a repository wake and does not use worker activation as a scheduling event.

## Production boundary

The first 4.18.18 candidate merge landed on `main` as `4fc4c79d05835caf39fe6bea7c45346cc99ceffe`. Final push CI run 668 passed, and production then advanced naturally without a manual restart to `daemon_version=4.18.18`, `self_revision=4fc4c79d05835caf39fe6bea7c45346cc99ceffe`, idle state, four-worker parallel supervisor. That proves the Local Agent daemon deployment, not the browser-extension live gate.

A follow-up candidate adds service-worker startup reconciliation for already-open stale content scripts so the required browser upgrade test can be performed without reloading the ChatGPT page or sending an unrelated wake.

4.18.18 must not be tagged/frozen until exact-head CI, Chromium, macOS ARM64 and a live `[LAB:HELP]` feedback auto-submit test all pass on the final candidate. The live test must reload only the unpacked extension, leave the ChatGPT tab unreloaded, prove v5 -> v6 replacement, and confirm Bridge submits `[LA_BRIDGE_FEEDBACK]` without operator interaction.
