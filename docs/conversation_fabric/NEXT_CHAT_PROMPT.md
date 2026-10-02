# Conversation Fabric continuation prompt

Use this prompt to start the next ChatGPT conversation. Repository state, durable documentation and fresh `host-ops` state are authoritative; do not rely on previous chat memory.

---

Continue Conversation Fabric in repository `MichalMatu/local-agent`.

Do not rely on memory from the previous chat. Repository state, durable docs and fresh `host-ops` state are the source of truth.

Read in this order first:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/conversation_fabric/CURRENT_PLAN.md`
4. `docs/DEVELOPMENT_PLAN.md`
5. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

Then fetch and verify fresh mutable state before any effect:

- `main`
- `develop/conversation-fabric`
- `host-ops:agent-control`
- `.agent/status/daemon.json`
- clean DEV checkout at `/Users/michal/local-agent-dev`
- production checkout at `/Users/michal/local-agent`

Current runtime baseline:

- production `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent 4.19.12 / Chat Bridge 0.6.2
- canonical development branch: `develop/conversation-fabric`
- accepted CODE checkpoint: `e76dc4a114f750cc0beabdbb2ad626d41ff2e986`
- accepted code commit: `Add durable child adoption and retirement`
- exact-SHA canonical CI run: `37054505079`
- all five jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`

Documentation-only commits may advance the canonical branch beyond the accepted CODE checkpoint. Fetch the fresh head and distinguish docs-only commits from runtime changes before effects.

Stage 8 automatic one-child proof is COMPLETE and closed. Do not start another Stage 8 spawn campaign.

Proof22 authority/evidence remains:

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- request digest: `sha256:460bb68b76a73350718a9f091bf3b071cfa8762f3222030e52af58e8b392a79d`
- transaction: `spawn-92f4107c2bf0bdd6abd122c5ddcfaa6417691c576d811efc6a1973f59c676615`
- canonical child: `https://chatgpt.com/c/6abfcdf9-8438-83eb-86da-1c4b209afc47`
- spawn attempt: `1`
- matching durable registration/completion evidence
- no manual attach/recovery
- no production mutation

The terminal/checkpoint milestone is COMPLETE on CODE `a16918d32bc366dbc9d8a8793669baa214d13620` with canonical CI `37036591713` fully green.

Accepted terminal path:

```text
active -> terminal_pending_evidence -> terminal_recorded
```

The adoption/retirement milestone is also COMPLETE on accepted CODE `e76dc4a114f750cc0beabdbb2ad626d41ff2e986`.

Preimplementation audit evidence:

- `conversation-adoption-retirement-preimplementation-audit-20261002-v1`: `done`
- `conversation-adoption-retirement-audit-summary-20261002-v1`: `done`

Accepted path:

```text
terminal_recorded
  -> durable adoption record
  -> workflow reasoning node succeeded
  -> retired
```

Accepted adoption/retirement properties:

- adoption requires exact admitted request, durable canonical registration, durable terminal record and child state `terminal_recorded`;
- adoption binds exact request digest, terminal-record digest, workflow ID and workflow-node ID;
- adoption is bounded and schema-validated;
- adoption persists before workflow-node success;
- crash after adoption persistence but before workflow advancement is recoverable through idempotent retry;
- identical semantic retries are idempotent and conflicting records fail closed;
- retirement requires durable adoption and the bound workflow node in `succeeded`;
- reload fails closed if retired state loses adoption, terminal evidence or succeeded workflow state;
- mutations reuse the workflow execution lock;
- no browser effect was introduced.

Verification evidence:

- `conversation-adoption-retirement-implementation-20261002-v2`: focused 47 tests passed;
- `conversation-adoption-retirement-candidate-verify-20261002-v1`: compile, Ruff, 56 focused/workflow tests and diff check passed;
- first integration v1 failed before source mutation because of patch-script encoding and is non-authoritative;
- DEV was synchronized clean to accepted CODE;
- production remained clean and unchanged.

Current milestone is restart/recovery proof across external-effect boundaries.

Do not begin with a live browser campaign. First perform one bounded read-only boundary inventory on the accepted CODE checkpoint. Re-open current code and durable evidence around:

- child spawn transaction and browser submit/canonical identity;
- child registration and spawn completion evidence;
- terminal evidence/state ordering;
- adoption record/workflow-node success ordering;
- retirement and any actual cleanup effect if one exists;
- workflow checkpoint/publication/evidence primitives used by these boundaries.

For every boundary identify:

- durable pre-effect intent/checkpoint;
- external effect;
- durable post-effect evidence/completion;
- observable restart states;
- safe retry, prohibited retry, or recovery/attach rule;
- ambiguity/conflict fail-closed behavior;
- existing tests/live proofs;
- smallest missing proof.

Persist this audit through `host-ops`. Do not mutate source during the audit.

If the audit identifies a missing deterministic restart/recovery contract, add focused failure-injection/restart tests and implement only the smallest gap. If the contract already exists, prove it without changing runtime behavior. Use a live browser effect only if the smallest missing proof truly crosses that browser boundary.

Use direct GitHub operations for repository-side inspection/changes and `host-ops` for every Mac-local checkout, synchronization, test, process or browser-profile operation.

Do not touch:

- production `main` without a separate explicit release decision;
- `chat-bridge-state`;
- `operator-control`;
- production Chrome profile `/Users/michal/Library/Application Support/Google/Chrome`.

Preserved Stage 8 isolated evidence remains:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`

Do not broaden the milestone into manual lifecycle parity, Browser Driver promotion, multi-child fan-out, fleet scheduling, rollover or broad Superchat automation.

First perform a short read-only preflight and report whether the restart/recovery boundary audit is safe to continue. If safe, continue autonomously with the bounded read-only audit and then only the smallest missing proof it identifies.
