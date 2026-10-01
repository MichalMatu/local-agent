# Current handoff — Conversation Fabric Stage 8

Date: 2026-10-01
Status: active handoff checkpoint

## Read this first

This file is the authoritative continuation checkpoint for the current Stage 8 work. Do not reconstruct the current state from older chat history.

Then read:

1. `AGENTS.md`
2. `docs/conversation_fabric/CURRENT_PLAN.md`
3. `docs/DEVELOPMENT_PLAN.md`

## Repository state

Production is unchanged:

- `main`: `0088f55ef37eecf26e0d4363f999797b9e340e96`
- Local Agent: v4.19.11
- Chat Bridge: 0.6.2

Conversation Fabric development:

- canonical branch: `develop/conversation-fabric`
- last runtime/code baseline: `b6f9ce3bb47309474dba7c430df3880912aaa4ef`
- baseline commit: `Wait for delayed DEV extension worker`
- the branch may contain later documentation-only handoff commits; always verify the actual GitHub head before work
- Mac DEV checkout: `/Users/michal/local-agent-dev`
- DEV state root: `/Users/michal/Library/Application Support/local-agent-dev`
- production checkout: `/Users/michal/local-agent`

Current temporary implementation branch:

- `work/conversation-composer-replacement`
- currently still at runtime/code baseline `b6f9ce3bb47309474dba7c430df3880912aaa4ef`
- no accepted composer-replacement commit exists yet

Operational and archive branches are not development targets:

- `chat-bridge-state`
- `operator-control`
- `archive/conversation-fabric-pre-rebase`

## What has been proven and fixed

### Pre-submit restart recovery

Stage 8 now supports both legal persistent-browser restart outcomes:

- the original transaction marker tab survives and is recovered; or
- the marker tab is missing while durable state still proves `bootstrap_ready`, allowing one bounded pre-submit reattach.

Strict lost-ACK recovery still never creates a replacement tab. A second unresolved reattach condition fails closed.

### Delayed extension worker startup

The live Mac proof exposed a startup race in `scripts/conversation_live_slice_browser.cjs`: the old implementation effectively waited about 300 ms for the MV3 extension service worker even though the intended bound was 8 seconds.

That race is fixed at runtime/code baseline `b6f9ce3bb47309474dba7c430df3880912aaa4ef` by bounded polling for the extension worker. The fix was validated with focused tests, browser smoke, exact-SHA CI and a cloned-profile Mac proof through `host-ops`.

## Preserved failed live proof

Do not retry, rewrite or delete this evidence.

The original live attempt reached the submit boundary and then failed closed:

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- transaction: `spawn-3c78a92eb001f46790989f4da8fea0bcca6b1d55035770b7dc48ef40bd72a032`
- attempt: `1`
- durable state: `ambiguous`
- durable journal phase: `ambiguous`
- failure: `live submit unresolved: spawn_composer_changed`
- `child_conversation_url`: `None`
- matching registration: absent
- live arm: consumed/absent

Important interpretation: `spawn_composer_changed` is returned by `spawn_content.js` before `writeClaim(..., "submitting")` and before `button.click()`. Therefore this specific failure occurred before the bootstrap was submitted. The durable `ambiguous` classification is intentionally preserved as historical evidence; do not hand-edit the transaction back to a pre-submit state.

## Current bug to finish

ChatGPT may replace the contenteditable composer DOM node after Local Agent inserts the bootstrap text. The current code treats DOM node identity replacement as `spawn_composer_changed` even when the replacement contains the exact same bootstrap text.

Required fix:

- tolerate a replaced composer node only when the currently active composer still contains exactly the inserted bootstrap text;
- never tolerate different text;
- preserve the existing operator-edit safety proof;
- preserve route, send-button, transaction, digest and claim checks;
- do not weaken the post-submit ambiguity boundary.

A browser regression test must explicitly simulate composer DOM replacement between insertion and the final pre-submit check.

## Exact next sequence

1. Start from `work/conversation-composer-replacement` at exact base `b6f9ce3bb47309474dba7c430df3880912aaa4ef`.
2. Implement the minimal composer-replacement fix in `chat_bridge/spawn_content.js`.
3. Add/repair the real browser smoke in `scripts/conversation_spawn_browser_smoke.cjs` so it proves both:
   - exact-text DOM replacement may continue;
   - operator-edited/different text still fails before submit.
4. Run focused tests and both Conversation Fabric browser smokes on Mac through `host-ops`.
5. Require exact-candidate full CI before promotion.
6. Fast-forward only `develop/conversation-fabric` after the candidate is green.
7. Keep the preserved ambiguous live attempt untouched.
8. Create a fresh isolated DEV live lab/state namespace for the next proof instead of reusing the ambiguous attempt.
9. Run exactly one fresh sequence: `seed -> prepare -> login -> arm -> run`.
10. Stop after the first successful one-child proof and inspect durable evidence.

## Success condition for Stage 8

The milestone is complete only when one fresh bounded proof produces all of the following:

- exactly one real child `https://chatgpt.com/c/<id>`;
- matching durable `ChildRegistration`;
- matching durable `SpawnTransaction=done`;
- bounded completion evidence tied to the admitted request/plan;
- no Local Agent task execution authority granted to the child;
- no production Chrome/profile mutation;
- no blind replay after any ambiguous external effect.

## Operating rules for the next conversation

- Use direct GitHub operations for repository inspection and repository-side changes.
- Use `host-ops` for every operation on the Mac: checkout updates, worktrees, local tests, browser/profile inspection and live proof execution.
- Before any live browser effect, verify the exact `develop/conversation-fabric` head, clean DEV checkout, current CI evidence and isolated DEV state.
- Never mutate `main`, `chat-bridge-state`, `operator-control` or the archive branch as part of Stage 8 development.
- Never retry the preserved ambiguous transaction.
- Do not start adoption, retirement, fleet scheduling, multi-child fan-out or broader lifecycle work before the one-child proof succeeds.

Exact GitHub state and durable local evidence outrank remembered chat context or browser appearance.
