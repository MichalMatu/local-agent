# Same-browser Superchat acceptance proof — 2026-10-04

Candidate branch: `work/superchat-same-browser-repair`.
Local Agent: 4.20.6. Chat Bridge: 0.8.3. Content protocol: 18.

## Live acceptance

The already-installed unpacked extension was updated in the user's ordinary authenticated Chrome. No CDP endpoint, profile copy or additional browser process was used for this acceptance run.

- Parent: [Bridge test readiness](https://chatgpt.com/c/6ac1e434-dbe0-83ed-866e-f1a0a8ac07d5).
- Campaign: `cf-b6d98cd015450fc1`.
- Research child: [sum-proof](https://chatgpt.com/c/6ac1eb5f-cae0-83eb-9abf-b2102c7ad718), captured result `SUM_PROOF=42`.
- Verification child: [product-proof](https://chatgpt.com/c/6ac1eb6a-9c64-83eb-b854-decaf3041e31), captured result `PRODUCT_PROOF=42`.

The parent emitted one native delegation control. Bridge created two background tabs in the same browser, submitted one prompt per child, automatically captured stable replies, saved both results, closed the owned tabs, and delivered one terminal feedback message. The visible parent synthesis was:

```text
LIVE_DELEGATION_OK SUM_PROOF=42 PRODUCT_PROOF=42
```

After a final extension reload, the durable receipt was inspected through the service-worker UI:

```json
{"protocol":18,"id":"cf-b6d98cd015450fc1","state":"completed","feedback_delivered":true,"cleanup_pending":false,"parent_enabled":false}
```

The test parent was paused after completion. The global Master setting was preserved. Test conversations remain available for review; diagnostic windows and owned child tabs were closed.

## Regressions addressed

- Rendered control markers may have collapsed newlines.
- Fresh SPA conversations retain a provisional sender document URL after the tab acquires its canonical conversation route.
- Assistant role headings can be siblings of the answer body. Result/control extraction now scopes the semantic assistant body and excludes surrounding rating UI and user text.
- Virtualized history can keep the visible user-message count constant. Exact new user-turn identity confirms submission.
- Extension reload can clear session tab claims and detach content listeners. Recovery requires the exact page transaction/request/bootstrap claim and current child URL; no prompt is replayed.
- Duplicate controls are serialized, failures retain evidence, and unclosed failed child tabs continue consuming global capacity.

An earlier pre-fix campaign failed explicitly and remains in the conversation history. The successful campaign above was a fresh authorized test, not a replay of that campaign.

## Automated verification

The real-extension offline browser proof covers two same-context children, exactly one bootstrap per child, semantic role headings with adjacent answer bodies and unrelated rating text, missing session claims, conflicting claim rejection, detached-listener reinjection, owned-tab cleanup, parent synthesis and suppression of repeat result feedback. DOM and Bridge browser suites additionally cover composer protection, SPA navigation, virtualized user confirmation and bounded native Retry.

Verification passed: 759 Python tests with full compile/lint/Node checks, 297 macOS smoke tests, and the complete Bridge browser profile. The final receipt-race change also passed the full focused Node suite and the real-extension delegation proof.

Logs are retained under `/tmp/local-agent-superchat-verify-final.log`, `/tmp/local-agent-superchat-macos.log`, `/tmp/local-agent-superchat-browser-final.log`, `/tmp/local-agent-superchat-node-final.log` and `/tmp/local-agent-fabric-e2e-final.log`.

## Scope

This live run proves reasoning delegation and transport using bounded arithmetic prompts. It does not claim an end-to-end repository mutation. Children remain reasoning-only, receive explicit source context in their prompts and do not inherit the parent history. The parent owns synthesis and any subsequent executable Local Agent task must use its actual target repository's canonical binding. Candidate changes are local; no release was tagged or published.
