# Conversation Fabric current plan

## Goal

Move production child-chat lifecycle into the operator's already authenticated primary Chrome session and then run one bounded live Superchat acceptance on real code.

The isolated-profile production approach is retired. It introduced an unnecessary second authentication boundary: ChatGPT login and Cloudflare verification can block child creation even while the operator's normal Chrome session is already healthy.

## Production browser model

Production Conversation Fabric uses:

- the operator's normal Chrome process;
- the existing authenticated ChatGPT session;
- the installed Chat Bridge extension;
- normal Chrome tabs for parent and child conversations;
- logical ownership through exact tab id, canonical child URL, spawn transaction id, request digest and bootstrap digest.

Production Conversation Fabric does **not**:

- launch another Chrome/Chromium process;
- create or migrate a separate ChatGPT profile;
- copy cookies/session files;
- require manual login in a child browser;
- treat Cloudflare/login recovery as a normal orchestration step.

Isolated Chromium remains test infrastructure for deterministic synthetic browser/extension coverage.

## Existing building blocks to reuse

Do not reimplement browser mechanics that already exist:

- `chat_bridge/worker_spawn.js` already contains transaction-safe child-tab creation, recovery and bootstrap submission primitives using `chrome.tabs` and `chrome.scripting`;
- Chat Bridge content scripts already interact with the ChatGPT composer and preserve operator edits fail-closed;
- canonical conversation URL and ownership checks already exist;
- GitHub remains durable control/evidence; Local Agent remains the only machine executor.

The implementation task is to make the live production Conversation Fabric path use these normal-Chrome Bridge primitives instead of `chromium.launchPersistentContext(...)`.

## Implementation sequence

1. Remove the separate-profile requirement from the production live child actuator path.
2. Route create/recover/probe/submit/reconcile/open/observe/close lifecycle operations through the installed Chat Bridge in the primary Chrome session.
3. Preserve exact transaction/tab ownership and fail closed on ambiguous or missing tabs.
4. Preserve bounded composer/readiness checks and duplicate-submit protection.
5. Keep isolated Chromium only in synthetic browser tests/CI.
6. Remove normal-flow manual login/profile migration from the acceptance path.
7. Add focused regression coverage proving production mode does not launch a second browser/profile.
8. Run exact-head CI and the relevant real Chrome/Bridge smoke.
9. Only then resume the bounded live Superchat acceptance.

## Live acceptance sequence after implementation

1. Verify current `main`, installed Local Agent `self_revision`, Chat Bridge version and the parent conversation control state.
2. Verify the normal Chrome session is already authenticated and Chat Bridge is active; do not start another browser.
3. Choose one small real-code goal in an execution-enabled repository.
4. Parent creates at least two reasoning-only children as normal tabs in the same Chrome session with non-overlapping assignments.
5. Give children pinned repository/commit context and a bounded output contract. No child may create `.agent/tasks` or run machine commands.
6. Parent reads both child results and records exact tab/conversation lifecycle evidence.
7. Parent reconciles disagreements and decides whether a code change is justified.
8. If execution is justified, parent creates exactly one bounded target-repository task with the exact canonical binding and a stable branch-scoped `dedupe_key`.
9. Observe one Local Agent execution/result and confirm no equivalent duplicate task/build/test runs.
10. Retire owned child tabs/lifecycle state and return scheduling/operator state to the intended paused state.
11. Record PASS / PARTIAL / FAIL with exact evidence and any single next blocker.

## Stop conditions

Stop rather than weakening safety if any of these occurs:

- the normal Chrome/Bridge session is not available;
- child tab ownership is ambiguous;
- two authoritative child generations appear for one child slot;
- a child obtains machine execution authority;
- target binding/repository identity is uncertain;
- equivalent expensive tasks execute twice;
- the parent cannot observe durable child result evidence.

A missing isolated profile, isolated-profile login failure or Cloudflare challenge is no longer a production blocker because that path is no longer part of the accepted production architecture.

## Success criteria

The milestone passes only when the user can visibly see one Superchat parent orchestrating real child tabs inside the existing Chrome session and, when needed, exactly one deterministic Local Agent execution on real code.
