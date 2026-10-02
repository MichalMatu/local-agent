# Current handoff — Conversation Fabric Stage 8

Date: 2026-10-02
Status: active handoff checkpoint; proof15 is prepared but not armed or run

## Read this first

This file is the authoritative continuation checkpoint for the current Stage 8 work. Do not reconstruct the current state from older chat history.

Then read:

1. `AGENTS.md`
2. `docs/conversation_fabric/CURRENT_PLAN.md`
3. `docs/DEVELOPMENT_PLAN.md`

Exact GitHub state and durable `host-ops` evidence outrank remembered chat context or browser appearance.

## Repository state

Production is unchanged by Stage 8 work:

- `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent: v4.19.12
- Chat Bridge: 0.6.2

Conversation Fabric development:

- canonical branch: `develop/conversation-fabric`
- accepted code head before this documentation update: `d65cbaacf70ee272e4263ab0e73428aa1376210e`
- accepted commit: `Wait for canonical child identity stabilization`
- Mac DEV checkout: `/Users/michal/local-agent-dev`
- production checkout: `/Users/michal/local-agent`

Current isolated live-lab root/profile:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- persistent isolated profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`
- production Chrome profile must never be used or copied: `/Users/michal/Library/Application Support/Google/Chrome`

The current profile is intentionally reused across proofs so the operator logs into ChatGPT once. Fresh proofs archive/reset only the live `state` and `logs`. A future cleanup may move the persistent DEV login profile to a root-independent path, but that is out of scope until the one-child proof is complete.

Operational/archive branches are not development targets:

- `chat-bridge-state`
- `operator-control`
- `archive/conversation-fabric-pre-rebase`

## What is already fixed and proven

### Persistent authenticated DEV profile

The live slice no longer tries to perform Google OAuth through Playwright. The supported model is:

1. one isolated persistent DEV Chrome profile;
2. manual sign-in once in normal Google Chrome when needed;
3. later Playwright sessions reuse the same profile;
4. the runner only verifies authentication and continues.

The login gate now requires an authenticated session, not merely a visible guest composer. It can confirm login through the account/profile control or the bounded `/api/auth/session` probe. Shared DEV Playwright and Chrome-for-Testing dependencies are auto-discovered; manual environment exports are not required for normal use.

### Manual recovery for an already-created ambiguous child

Stage 8 now has an explicit `live_flow attach` path for a child that was physically created but whose canonical URL was not durably captured before the browser session closed. `attach` never opens the browser and never re-submits the bootstrap. It records the existing child registration while preserving the original ambiguous spawn transaction as historical evidence.

### Provisional ChatGPT route handling

The browser may pass through both of these provisional forms after first submit:

- `/uc/<id>`
- `/c/local-chatgpt%3A<uuid>`

They are not canonical child identities. The accepted code waits for a valid canonical `/c/<id>` and keeps the JS URL validator aligned with the stricter Python conversation contract.

Accepted checkpoint:

- `7ceb2fa7b4a8ec037f2d526341a6a0acd34c55f5` — `Handle local ChatGPT provisional conversation routes`

The synthetic browser proof covers a local placeholder lasting longer than the inner five-second content wait and confirms the outer bounded transition wait succeeds.

### Bounded login probe startup

A short login probe previously gave `page.goto()` its own timeout and then started a second full timeout window, allowing the Python wrapper to expire before the Node actuator returned. The current implementation uses one real deadline and gives the cold existing-session probe 20 seconds.

Accepted checkpoint:

- `06cf93f4693f81561f00100977a32f9adbbf9729` — `Bound persistent login probe startup time`

### Fresh-chat composer stabilization

Proof13 showed that a newly created ChatGPT tab can reach the fresh route before the composer exists. A five-second pre-submit readiness window was too short. The actuator now gives content injection a short bounded window and, once the content script is reachable on the fresh route, gives the composer up to 30 seconds to stabilize before declaring `spawn_composer_not_found`.

Accepted checkpoint:

- `30a8d952ac8a9c2361c0aa4e6eed16a35c4ab71b` — `Wait for fresh chat composer stabilization`

Regression evidence includes a synthetic composer appearing after 6.5 seconds.

### Canonical child identity stabilization

Proof14 showed a second stabilization race after submit: the browser had already reached a canonical child route, but the exact user-message DOM used to bind the identity was not ready yet. The route was therefore real, but the old code returned `spawn_submission_ambiguous` immediately.

The current code waits up to 30 seconds after canonical `/c/<id>` discovery for the exact submitted user message to appear, while continuously requiring the claimed tab and canonical child route to remain unchanged. It still fails closed if the route changes or identity cannot be confirmed.

Current accepted code checkpoint:

- `d65cbaacf70ee272e4263ab0e73428aa1376210e` — `Wait for canonical child identity stabilization`

Focused validation on Mac through `host-ops` passed:

- 24 focused Python live-runner/live-flow tests;
- bounded live-slice browser restart/recovery smoke;
- `/uc` and `local-chatgpt` transition smoke;
- delayed canonical-child user-message identity smoke;
- Chat Bridge control protocol tests.

No GitHub commit status/check is currently recorded for exact SHA `d65cbaa...`; do not claim exact-SHA full CI for this checkpoint unless it is run and recorded later.

## Preserved live evidence

### Proof12 — real child physically created; manual attach recovery

Proof12 proved the end-to-end browser effect itself works:

- transaction: `spawn-6bc0561cd77398dc2a346c7a059cb318169c763f7010653904661dc97a8009b4`
- submitted bootstrap produced a real ChatGPT child;
- recovered canonical child: `https://chatgpt.com/c/6abf09ed-9bbc-83ed-a688-4bf9a9ab39f4`
- Chrome history showed the provisional local route immediately before canonical `/c/...`;
- automatic run ended `spawn_submission_ambiguous` because identity was not captured in time;
- automatic retry/re-arm was correctly forbidden;
- explicit manual attach completed durable registration without another submit;
- final child lifecycle became `active` and live status became healthy;
- original spawn transaction intentionally remained `ambiguous` as historical evidence.

Do not reinterpret proof12 as an automatic Stage 8 success. It proves real creation plus safe recovery, not automatic `SpawnTransaction=done`.

### Proof13 — pre-submit composer stabilization failure

At `06cf93f...`:

- transaction: `spawn-df6b6d0bf43dd994e8f86078a535fcc4717b1c924137ecd42873e2f01c5176a4`
- run paused safely at `bootstrap_ready`;
- reason: `spawn_composer_not_found`;
- no submit occurred;
- state remained recoverable and `needs_rearm=true`.

This exposed the fresh-chat composer stabilization race and led to `30a8d952...`.

### Proof14 — submit succeeded far enough to reach child route; identity DOM lagged

At `30a8d952...`:

- transaction: `spawn-5af74a34349a69b97e3f2fcb0cf007d4c1ae81713e6edf787b2d748a0755038a`
- browser result reported `browser_route="child"`;
- run ended `manual_attach_required` / `spawn_submission_ambiguous`;
- transaction became terminal `ambiguous`;
- `needs_rearm=false`;
- automatic retry was correctly forbidden.

This is the evidence that canonical child routing can stabilize before the exact user-message DOM used for identity confirmation. It led to `d65cbaa...`.

Proof14 state/logs were archived before proof15. Never retry proof14.

## Current live checkpoint — proof15

Proof15 is fresh and prepared on exact code SHA `d65cbaacf70ee272e4263ab0e73428aa1376210e`.

Current durable authority:

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- request digest: `sha256:799ca488d7de2b2c0049f2dc0a23e16028be46edaf3ba6873c88b0240e5227cd`
- transaction: `spawn-7fc29442cd190d48e9af2e3a2fec5664c18bf5f29dd182527e1126fe1c45b677`
- plan digest: `sha256:70ced439858a6a7e1b580d83263eeca333b52418c99b05c5e2027696d6c0ee44`
- repository commit admitted by the request: `d65cbaacf70ee272e4263ab0e73428aa1376210e`
- child state: `requested`
- live slice: prepared
- arm: not created
- run: not executed

This is the correct continuation point. Do not reseed proof15 unless its prepared authority is first shown to be invalid.

## Exact next sequence

1. Fetch fresh GitHub refs and verify `develop/conversation-fabric` still contains `d65cbaa...` (or understand any later documentation-only commits) and production `main` is still `979ef080...`.
2. Verify the Mac DEV checkout is clean and corresponds to the accepted code checkpoint before any browser effect.
3. Inspect proof15 status read-only and require the expected plan digest and transaction above.
4. Reuse the existing isolated persistent browser profile. Run `login` only as authentication verification; do not perform another OAuth login unless the profile is actually logged out.
5. If exact-SHA full CI is required by the operator gate, establish and record it before the live submit. Current handoff only has focused Mac validation for `d65cbaa...`.
6. `arm` proof15 exactly once with the prepared plan digest.
7. Capture the returned launch nonce.
8. `run` exactly once with that nonce.
9. Never automatically retry or re-arm after an ambiguous/potentially submitted outcome.
10. If run returns `completed`, inspect durable transaction, registration and result evidence before doing anything else.
11. If run is ambiguous, stop and inspect the existing child only; `manual attach` is allowed only for deterministic recovery of that already-created child and must never cause a second submit.

## Stage 8 success condition

Stage 8 automatic one-child proof is complete only when one fresh bounded run produces all of the following for the same request:

- exactly one real child `https://chatgpt.com/c/<id>`;
- matching durable `ChildRegistration`;
- matching durable `SpawnTransaction=done`;
- bounded completion evidence tied to the admitted request/plan;
- no Local Agent task execution authority granted to the child;
- no production Chrome/profile mutation;
- no blind replay after any ambiguous external effect.

Proof12 manual attach is valuable recovery evidence but does not satisfy the automatic `SpawnTransaction=done` gate.

## Operating rules for the next conversation

- Use direct GitHub operations for repository inspection and repository-side changes.
- Use `host-ops` for every operation on the Mac: checkout updates, local tests, browser/profile inspection and live proof execution.
- Never mutate production `main`, `chat-bridge-state`, `operator-control` or the archive branch as part of Stage 8 development.
- Never use, copy or inspect raw authentication secrets from the production Chrome profile.
- Never retry a transaction after submit may have occurred.
- Keep one authority step per `live_flow` invocation: `login -> arm -> run`.
- Do not start adoption, retirement, fleet scheduling, multi-child fan-out or broader lifecycle work before the automatic one-child completion gate succeeds.

## Recovery rule

If a future conversation is unsure where to continue, use this handoff plus `docs/conversation_fabric/CURRENT_PLAN.md` as the checkpoint tie-breaker, then verify every mutable fact against GitHub and `host-ops` before effects.