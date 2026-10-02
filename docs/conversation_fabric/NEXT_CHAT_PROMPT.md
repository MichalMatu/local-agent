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
- accepted CODE checkpoint: `2557f9477ff34ebb5b8502a15747e5d78f29bd5a`
- accepted code commit: `Add restart recovery boundary proofs`
- exact-SHA canonical CI run: `37056289262`
- all five jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`
- this accepted checkpoint is test-only relative to the prior adoption/retirement runtime checkpoint; runtime behavior did not change

Documentation-only commits may advance the canonical branch beyond the accepted CODE checkpoint. Fetch the fresh head and distinguish docs-only commits from runtime/test changes before effects.

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

The adoption/retirement milestone is COMPLETE on CODE `e76dc4a114f750cc0beabdbb2ad626d41ff2e986` with canonical CI `37054505079` fully green.

Accepted path:

```text
terminal_recorded
  -> durable adoption record
  -> workflow reasoning node succeeded
  -> retired
```

The restart/recovery boundary-proof milestone is COMPLETE on accepted CODE `2557f9477ff34ebb5b8502a15747e5d78f29bd5a`.

Durable boundary audit evidence:

- `conversation-restart-recovery-boundary-summary-20261002-v2`: `done`, read-only

The audit found no missing runtime recovery contract. Existing runner and Chromium/MV3 evidence already proved:

- lost browser-create ACK recovers the same transaction/tab and never creates a replacement;
- pre-submit restart performs strict recovery or one bounded reattach only before submit;
- `bootstrap_submitting` restart reconciles rather than resubmitting;
- MV3 termination during submit recovers the same canonical child without a second submit;
- ambiguous submission fails closed and requires manual attach;
- terminal/adoption ordering already had restart failure-injection proofs.

The only missing explicit evidence was B4-B6 runner restart coverage:

```text
identity_discovered -> registration_submitting
registration_submitting -> ChildRegistration -> done
done + ChildRegistration -> completion evidence/cleanup
```

Those proofs were added in `tests/test_conversation_restart_recovery.py`; no runtime source changed.

Verification evidence:

- `conversation-restart-recovery-proof-verify-20261002-v1`: compile, Ruff, 49 focused tests and diff check passed;
- a local `bridge-browser` attempt failed only because the DEV checkout did not expose the `playwright` Node module and made no source changes;
- exact-SHA GitHub CI installed isolated browser tooling and passed `bridge-browser` and every other job;
- production remained clean and unchanged.

Current milestone is manual lifecycle parity.

Do not begin by creating a new child or launching a browser campaign. First perform one bounded read-only ownership/contract audit on accepted CODE `2557f9477ff34ebb5b8502a15747e5d78f29bd5a`.

Re-open current code and tests around:

- `attach_ambiguous_live_slice` and related manual recovery entrypoints in `local_agent/development/live_runner.py`;
- conversation registration/state ownership in `local_agent/conversation/store.py`;
- spawn ambiguity/queue ownership in `local_agent/conversation/spawn_store.py`;
- terminal evidence/state ordering in `local_agent/conversation/terminal.py`;
- adoption/retirement in `local_agent/conversation/adoption.py`;
- workflow reasoning-node state/store contracts.

For every manual lifecycle operation identify:

- durable authority and preconditions;
- exact request/transaction/child binding;
- state transition and evidence ordering;
- idempotency and conflict behavior;
- restart/resume behavior;
- whether browser access is actually required;
- existing positive/negative tests;
- smallest missing parity proof or contract.

The target is one lifecycle shared by automatic and manual paths. Do not introduce a second scheduler, alternate lifecycle store or browser-owned durable state.

Persist the audit through `host-ops`. Do not mutate source during the audit.

If the audit identifies a missing deterministic parity contract, add focused positive/negative/idempotency/restart tests and implement only the smallest gap. Reuse existing registration, terminal, adoption and retirement APIs whenever possible. Use a live browser effect only if the smallest missing proof truly requires it.

Use direct GitHub operations for repository-side inspection/changes and `host-ops` for every Mac-local checkout, synchronization, test, process or browser-profile operation.

Do not touch:

- production `main` without a separate explicit release decision;
- `chat-bridge-state`;
- `operator-control`;
- production Chrome profile `/Users/michal/Library/Application Support/Google/Chrome`.

Preserved Stage 8 isolated evidence remains:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`

Do not broaden the milestone into Browser Driver promotion, multi-child fan-out, fleet scheduling, rollover or broad Superchat automation.

First perform a short read-only preflight and report whether the manual lifecycle parity audit is safe to continue. If safe, continue autonomously with the bounded audit and then only the smallest gap it identifies.