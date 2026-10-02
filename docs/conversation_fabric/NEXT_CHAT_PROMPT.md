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

Then fetch and verify fresh mutable state before any effect:

- `main`
- `develop/conversation-fabric`
- `host-ops:agent-control`
- `.agent/status/daemon.json`
- clean DEV checkout at `/Users/michal/local-agent-dev`
- production checkout at `/Users/michal/local-agent`

Current durable baseline:

- production `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent 4.19.12 / Chat Bridge 0.6.2
- canonical development branch: `develop/conversation-fabric`
- accepted Stage 8 CODE checkpoint: `93fb65204db03c54d0080803d26266f3c06d777e`
- accepted code commit: `Confirm spawn identity from owned route transition`
- exact-SHA CI run: `37022787748`
- CI gate for that code checkpoint: all five jobs passed (`test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`)

Stage 8 automatic one-child proof is COMPLETE.

Proof22 authority/evidence:

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- request digest: `sha256:460bb68b76a73350718a9f091bf3b071cfa8762f3222030e52af58e8b392a79d`
- transaction: `spawn-92f4107c2bf0bdd6abd122c5ddcfaa6417691c576d811efc6a1973f59c676615`
- plan digest: `sha256:43581f5fc966859b7339ddbdb0cc24de26fbe3ec30841784bc851ebd322dc61a`
- canonical child: `https://chatgpt.com/c/6abfcdf9-8438-83eb-86da-1c4b209afc47`
- spawn attempt: `1`
- durable `SpawnTransaction=done`
- matching durable `ChildRegistration`
- child lifecycle: `active`
- bounded completion evidence: present and matching
- manual attach/recovery: not used
- production mutation: none

Do NOT start another spawn campaign. Stage 8 automatic child creation is already proven.

Current milestone is checkpoint and terminal recording for an already registered active child:

```text
active
  -> terminal_pending_evidence
  -> terminal_recorded
```

The preimplementation audit for this milestone has already completed successfully through `host-ops`:

- task/result: `conversation-terminal-evidence-preimplementation-audit-20261002-v1`
- audit was read-only
- it ran against clean code checkpoint `93fb65204db03c54d0080803d26266f3c06d777e`
- it inspected conversation state/store contracts plus existing workflow checkpoint/evidence and locking/atomic-write patterns

The first implementation task did NOT execute:

- task/result: `conversation-terminal-record-implementation-20261002-v1`
- result: `failed`
- failure: `invalid_task_file`
- parser error: `JSONDecodeError: Invalid control character at: line 12 column 2004 (char 2309)`
- `started_at=null`
- therefore no implementation commands ran and no source mutation from that task may be assumed

Do not replay that malformed task file as authority. It may be inspected only as a non-authoritative draft. Re-derive the smallest implementation from current repository contracts plus the completed audit.

Required terminal/checkpoint properties remain:

- `active -> terminal_pending_evidence` is explicit and durable;
- `terminal_recorded` is impossible without durable terminal evidence;
- terminal evidence binds to the exact child request digest and canonical registration;
- evidence is schema-validated and bounded;
- identical recording is idempotent;
- conflicting evidence fails closed;
- mutations serialize through the existing workflow execution/mutation locking model;
- persisted evidence/state survives reload/restart validation;
- positive and negative tests cover missing registration/evidence, conflict and invalid lifecycle ordering;
- no adoption/retirement semantics yet;
- no new browser effect is required for this deterministic storage/state slice.

Continuation sequence:

1. Verify fresh GitHub refs and `host-ops`/daemon state.
2. Verify the DEV checkout is clean and identify whether it is still at the accepted code checkpoint or has only intentional documentation-only commits ahead.
3. Read the completed audit result before editing.
4. Confirm the failed implementation task had no effects; do not reuse it blindly.
5. Inspect `local_agent/conversation/contract.py`, `state.py`, `store.py`, `tests/test_conversation_store.py` and the existing workflow checkpoint/evidence patterns identified by the audit.
6. Implement the smallest terminal evidence + recording slice with tests.
7. Use direct GitHub operations for repository-side inspection/changes where appropriate; use `host-ops` for every Mac-local checkout/test operation.
8. Run focused positive/negative conversation tests on Mac.
9. Run repository verification appropriate to the actual diff.
10. Push one reviewed CODE checkpoint to `develop/conversation-fabric` and establish exact-SHA CI before any further lifecycle proof.
11. Update `docs/CURRENT_HANDOFF.md` and `docs/conversation_fabric/CURRENT_PLAN.md` when the accepted checkpoint changes.

Do not touch:

- production `main` unless there is a separate explicit release decision;
- `chat-bridge-state`;
- `operator-control`;
- production Chrome profile `/Users/michal/Library/Application Support/Google/Chrome`.

Preserved Stage 8 isolated profile/root remain evidence only unless a later milestone explicitly needs browser work:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- persistent profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`

First perform a short read-only preflight and report whether the terminal/checkpoint implementation slice is safe to continue. If safe, continue autonomously with the smallest bounded implementation according to the durable plan.
