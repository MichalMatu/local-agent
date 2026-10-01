# Conversation Fabric — current execution plan

Status: canonical Stage 8 execution ledger.

## Current baseline

Production remains unchanged:

- `main@0088f55ef37eecf26e0d4363f999797b9e340e96`
- Local Agent v4.19.11
- Chat Bridge 0.6.2

Canonical development:

- `develop/conversation-fabric@b6f9ce3bb47309474dba7c430df3880912aaa4ef`

Current temporary candidate branch:

- `work/conversation-composer-replacement`
- current head is still the development baseline above
- no accepted composer-replacement commit exists yet

## Stage 8 goal

Prove one exact durable reasoning-child request can create exactly one real ChatGPT child in the isolated DEV browser profile, discover its canonical identity and persist matching durable evidence without granting child execution authority.

Required sequence:

```text
seed -> prepare -> login -> arm -> run
```

Each command is one authority step. Never auto-chain.

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

### 1. Restart marker recovery

Persistent Chromium may either restore or lose the transaction marker tab after a controlled restart. The runner now handles both bounded cases:

- recover the existing exact transaction tab; or
- while durable state still proves `bootstrap_ready`, perform one bounded pre-submit reattach.

Strict create lost-ACK recovery never creates a replacement tab. Reattach is not repeatable indefinitely.

### 2. Delayed MV3 extension worker startup

The Mac proof exposed a race where the browser actuator effectively abandoned extension-worker discovery after about 300 ms. The current baseline waits with a bounded 8-second polling window.

The accepted fix is:

- `b6f9ce3bb47309474dba7c430df3880912aaa4ef` — `Wait for delayed DEV extension worker`

## Preserved live evidence

The first live proof must remain immutable evidence and must not be retried.

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- transaction: `spawn-3c78a92eb001f46790989f4da8fea0bcca6b1d55035770b7dc48ef40bd72a032`
- attempt: `1`
- final durable state: `ambiguous`
- journal: `ambiguous`
- reason: `live submit unresolved: spawn_composer_changed`
- child URL: absent
- registration: absent
- arm: consumed

`spawn_composer_changed` is emitted before the content script writes the submission claim and before it clicks Send. Therefore this specific live failure is known to be pre-submit even though the durable transaction remains conservatively terminal `ambiguous`.

Do not edit, reset or reuse this attempt.

## Active blocker

The ChatGPT composer can be replaced in the DOM after the bootstrap input event. The current content script treats object identity change as an operator edit even when the new active composer still contains the exact bootstrap text.

The fix must preserve value-based safety:

- if the active composer text differs from the inserted bootstrap text, fail before submit;
- if the node was replaced but the active composer still contains exactly the inserted bootstrap text, it may continue;
- operator edits must remain untouched and unsent;
- route, digest, transaction, send-button and claim checks remain mandatory;
- post-click or otherwise genuinely ambiguous outcomes remain fail closed.

## Candidate implementation/test plan

Work only on `work/conversation-composer-replacement` until validated.

Required code scope:

- `chat_bridge/spawn_content.js`
- `scripts/conversation_spawn_browser_smoke.cjs`

Required regression evidence:

1. exact-text composer DOM replacement between insertion and final submit check succeeds once;
2. different/operator-edited text returns a pre-submit failure and is never clicked;
3. existing wrong-route, wrong-claim, duplicate-submit and ambiguous post-submit tests stay green;
4. `scripts/conversation_live_slice_browser_smoke.cjs` stays green;
5. focused Python live-runner/live-flow tests stay green.

All Mac-local work, worktrees, browser tests and profile inspection must be executed through `host-ops`.

## Promotion gate

Before moving the composer fix to `develop/conversation-fabric`:

1. exact candidate branch/head identified;
2. candidate diff limited to the intended scope;
3. focused tests green;
4. real browser smokes green on Mac through `host-ops`;
5. full exact-SHA CI green;
6. `develop/conversation-fabric` rechecked for drift;
7. fast-forward promotion only; no force update.

## Fresh final proof

After promotion, do not repair the preserved ambiguous attempt. Create a fresh isolated DEV live state namespace and run a new proof from the beginning:

```text
seed -> prepare -> login -> arm -> run
```

Before each live-effect step, recheck the exact source SHA, clean DEV checkout and current durable state. Do not automatically retry a failed `run`.

The final proof succeeds only when all of these exist for the same fresh request:

- exactly one `https://chatgpt.com/c/<id>`;
- exact matching `ChildRegistration`;
- exact matching `SpawnTransaction=done`;
- bounded completion evidence;
- no production profile mutation;
- no child execution authority.

Stop there and review evidence before starting any later lifecycle work.

## Out of scope until Stage 8 succeeds

Do not start:

- adoption or retirement;
- terminal/checkpoint lifecycle expansion;
- multi-child fan-out;
- fleet scheduling;
- rollover;
- broad Superchat automation;
- larger acceptance campaigns.

For current operational facts, use `docs/CURRENT_HANDOFF.md`. For longer-term milestone ordering, use `docs/DEVELOPMENT_PLAN.md`.
