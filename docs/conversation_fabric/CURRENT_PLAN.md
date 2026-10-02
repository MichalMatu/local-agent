# Conversation Fabric — current execution plan

Status: canonical Stage 8 execution ledger.

## Current baseline

Production remains unchanged by Stage 8:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent v4.19.12
- Chat Bridge 0.6.2

Canonical development branch:

- `develop/conversation-fabric`
- accepted code checkpoint before the current documentation updates: `d65cbaacf70ee272e4263ab0e73428aa1376210e`
- accepted commit: `Wait for canonical child identity stabilization`
- later documentation-only commits may advance the branch head; always distinguish code checkpoint from doc-only head before live work

Mac DEV checkout:

- `/Users/michal/local-agent-dev`

Current isolated live root/profile:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- browser profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`

The browser profile is deliberately persistent across proof state resets so ChatGPT login is reused. Production Chrome is never a source profile.

## Stage 8 goal

Prove one exact durable reasoning-child request can create exactly one real ChatGPT child in the isolated DEV browser profile, discover its canonical identity and persist matching durable evidence without granting child execution authority.

Authority sequence:

```text
seed -> prepare -> login -> arm -> run
```

Each command is one authority step. Never auto-chain effects.

## Non-negotiable invariants

- GitHub is the durable control/evidence plane.
- Chat Bridge is only a bounded browser actuator.
- Local Agent remains deterministic and model-free.
- `local-agent` remains `execution_enabled=false` for this proof.
- one parent, one reasoning child, one `ChildRequest`, one browser spawn attempt per proof;
- isolated DEV checkout/profile/state only;
- no production Chrome/profile mutation;
- no Native Messaging control plane;
- no blind replay after any potentially submitted ambiguous effect;
- child chats never gain independent Mac/task execution authority.

## Completed Stage 8 fixes

### Restart and pre-submit recovery

The runner can recover the exact transaction marker tab after a controlled restart. If durable state still proves `bootstrap_ready` and the original marker tab is gone, one bounded pre-submit reattach is allowed. Create lost-ACK recovery never blindly creates another replacement tab.

### Delayed MV3 extension worker startup

Extension-worker discovery uses bounded polling instead of the old sub-second race.

### Composer replacement safety

ChatGPT may replace the contenteditable composer after input. The current submit path compares the active composer value, not stale DOM object identity: an exact bootstrap-text replacement may continue; changed/operator-edited text still fails before submit.

### Authenticated persistent profile

The live runner no longer treats a guest composer as authenticated readiness. Login is manual once in normal Chrome if needed, then reused through the same persistent isolated profile. The auth gate uses the logged-in account control and a bounded session probe. Shared DEV Playwright/Chrome dependencies are auto-discovered.

### Explicit manual attach recovery

If submit physically created a child but automatic identity capture ended ambiguous, `live_flow attach --child-conversation-url ...` can register that already-existing child without opening the browser or resubmitting. The ambiguous transaction remains preserved as historical evidence.

### Provisional route classification

Accepted checkpoint:

- `7ceb2fa7b4a8ec037f2d526341a6a0acd34c55f5` — `Handle local ChatGPT provisional conversation routes`

The system now treats `/uc/<id>` and `/c/local-chatgpt%3A<uuid>` as provisional, never as final child identity. It waits for a canonical `/c/<id>` while preserving fail-closed behavior.

### Login-probe time budgeting

Accepted checkpoint:

- `06cf93f4693f81561f00100977a32f9adbbf9729` — `Bound persistent login probe startup time`

The short existing-session probe uses one deadline including navigation and allows 20 seconds for a cold Chrome/ChatGPT start, preventing wrapper timeout races.

### Fresh composer stabilization

Accepted checkpoint:

- `30a8d952ac8a9c2361c0aa4e6eed16a35c4ab71b` — `Wait for fresh chat composer stabilization`

After a new fresh route becomes reachable, the pre-submit actuator waits up to 30 seconds for the composer to stabilize. Browser regression coverage includes a composer appearing after 6.5 seconds.

### Canonical child identity stabilization

Current accepted code checkpoint:

- `d65cbaacf70ee272e4263ab0e73428aa1376210e` — `Wait for canonical child identity stabilization`

Canonical `/c/<id>` may appear before the exact submitted user-message DOM. The route-transition layer now waits up to 30 seconds for identity confirmation while continuously requiring the same claimed tab and canonical child URL. A route change or unresolved identity remains ambiguous/fail-closed.

Focused Mac validation for `d65cbaa...` passed:

- 24 focused Python tests;
- live-slice bounded restart/recovery browser smoke;
- provisional `/uc` transition smoke;
- provisional `local-chatgpt` transition smoke;
- delayed canonical child user-message identity smoke;
- Chat Bridge control protocol tests.

No exact-SHA GitHub commit status/check is recorded for `d65cbaa...` at this checkpoint. Do not claim full CI until evidence exists.

## Live proof ledger

### Proof12 — real child + safe manual recovery

- transaction: `spawn-6bc0561cd77398dc2a346c7a059cb318169c763f7010653904661dc97a8009b4`
- canonical child recovered from the isolated profile: `https://chatgpt.com/c/6abf09ed-9bbc-83ed-a688-4bf9a9ab39f4`
- automatic result: `spawn_submission_ambiguous`
- automatic retry: forbidden
- manual attach: completed registration without another submit
- lifecycle after attach: `active`
- transaction: intentionally remains `ambiguous`

This proves the browser can physically create the child and that fail-closed recovery works. It does not satisfy the automatic `SpawnTransaction=done` gate.

### Proof13 — safe pre-submit pause

At `06cf93f...`:

- transaction: `spawn-df6b6d0bf43dd994e8f86078a535fcc4717b1c924137ecd42873e2f01c5176a4`
- result: `paused`
- spawn state: `bootstrap_ready`
- reason: `spawn_composer_not_found`
- submit did not occur
- `needs_rearm=true`

This led to `30a8d952...`.

### Proof14 — canonical child route before exact message identity

At `30a8d952...`:

- transaction: `spawn-5af74a34349a69b97e3f2fcb0cf007d4c1ae81713e6edf787b2d748a0755038a`
- browser route: `child`
- result: `manual_attach_required`
- spawn state: `ambiguous`
- reason: `live submit unresolved: spawn_submission_ambiguous`
- `needs_rearm=false`

This proved submit had crossed into a real child route while identity confirmation still lagged. It led to `d65cbaa...`. Proof14 must never be retried.

## Current checkpoint — proof15 prepared

Proof15 has been freshly seeded and prepared on exact admitted code SHA `d65cbaacf70ee272e4263ab0e73428aa1376210e` after archiving proof14 state/logs. The persistent browser profile was kept unchanged.

Durable authority:

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- request digest: `sha256:799ca488d7de2b2c0049f2dc0a23e16028be46edaf3ba6873c88b0240e5227cd`
- transaction: `spawn-7fc29442cd190d48e9af2e3a2fec5664c18bf5f29dd182527e1126fe1c45b677`
- plan digest: `sha256:70ced439858a6a7e1b580d83263eeca333b52418c99b05c5e2027696d6c0ee44`
- child lifecycle: `requested`
- prepared: yes
- armed: no
- run: not executed

Do not reseed proof15 unless read-only verification shows the prepared authority is invalid.

## Exact continuation plan

1. Verify fresh GitHub refs: production `main` and the accepted Conversation Fabric code checkpoint.
2. Verify `/Users/michal/local-agent-dev` is clean and contains the accepted code before browser effects.
3. Read proof15 status and require its plan digest/transaction to match this ledger.
4. Reuse the persistent isolated profile; run `login` as readiness verification only.
5. Establish exact-SHA CI if required by the release/qualification gate; current ledger has focused Mac validation but no recorded exact-SHA status for `d65cbaa...`.
6. `arm` exactly once using proof15 plan digest.
7. Capture the nonce.
8. `run` exactly once.
9. Never auto-retry/re-arm after a potentially submitted ambiguous result.
10. On `completed`, inspect durable child registration, transaction and result evidence before any new work.
11. On ambiguity, stop. Recover only the already-created child; never cause a second submit.

## Completion gate

The automatic Stage 8 one-child milestone is complete only when one fresh bounded run has all of:

- canonical child `https://chatgpt.com/c/<id>`;
- matching durable `ChildRegistration`;
- matching durable `SpawnTransaction=done`;
- bounded completion evidence tied to the exact admitted request/plan;
- no production profile mutation;
- no child execution authority.

Proof12 manual attach remains recovery evidence, not automatic completion evidence.

## Out of scope until Stage 8 succeeds

Do not start:

- adoption or retirement;
- terminal/checkpoint lifecycle expansion;
- multi-child fan-out;
- fleet scheduling;
- rollover;
- broad Superchat automation;
- larger acceptance campaigns;
- root-independent shared DEV browser-profile refactoring.

For operational continuation use `docs/CURRENT_HANDOFF.md`. For longer-term ordering use `docs/DEVELOPMENT_PLAN.md`.