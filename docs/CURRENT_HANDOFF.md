# Current handoff — Conversation Fabric after Stage 8

Date: 2026-10-02
Status: Stage 8 automatic one-child milestone completed; next milestone is checkpoint and terminal recording

## Read this first

This file is the authoritative operational continuation point for Conversation Fabric work. Do not reconstruct current state from older chat history.

Then read:

1. `AGENTS.md`
2. `docs/conversation_fabric/CURRENT_PLAN.md`
3. `docs/DEVELOPMENT_PLAN.md`

Exact GitHub state and durable `host-ops` evidence outrank remembered chat context or browser appearance.

## Repository state

Production remains unchanged:

- `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent: v4.19.12
- Chat Bridge: 0.6.2

Conversation Fabric development:

- canonical branch: `develop/conversation-fabric`
- accepted Stage 8 code checkpoint before this documentation update: `93fb65204db03c54d0080803d26266f3c06d777e`
- accepted commit: `Confirm spawn identity from owned route transition`
- exact-SHA GitHub Actions run: `37022787748`
- all jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`
- Mac DEV checkout: `/Users/michal/local-agent-dev`
- production checkout: `/Users/michal/local-agent`

The isolated Stage 8 live root/profile remains preserved for evidence:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- persistent isolated profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`
- production Chrome profile must never be used or copied: `/Users/michal/Library/Application Support/Google/Chrome`

Later documentation-only commits may advance `develop/conversation-fabric`. Always distinguish the accepted code checkpoint from a doc-only branch head before effects.

## Stage 8 completion

Stage 8 required one exact durable reasoning-child request to create exactly one real ChatGPT child automatically, discover its canonical identity, and persist matching durable evidence without granting child execution authority.

Proof22 completed this gate automatically on code checkpoint `93fb65204db03c54d0080803d26266f3c06d777e`.

Exact authority/evidence:

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- request digest: `sha256:460bb68b76a73350718a9f091bf3b071cfa8762f3222030e52af58e8b392a79d`
- transaction: `spawn-92f4107c2bf0bdd6abd122c5ddcfaa6417691c576d811efc6a1973f59c676615`
- plan digest: `sha256:43581f5fc966859b7339ddbdb0cc24de26fbe3ec30841784bc851ebd322dc61a`
- canonical child: `https://chatgpt.com/c/6abfcdf9-8438-83eb-86da-1c4b209afc47`
- spawn attempt: `1`
- durable spawn state: `done`
- durable child lifecycle: `active`
- matching durable `ChildRegistration`: present
- completion evidence: present
- manual attach/recovery: not used
- production `main`: unchanged

The isolated Chrome History also showed exactly one canonical `/c/...` URL in the bounded transition window after the matching provisional route.

## Identity model accepted by Stage 8

Long ChatGPT user messages may be visually collapsed and lazily rendered behind `Show more`, so the full submitted bootstrap is not a stable post-submit DOM identity source.

The accepted identity chain is instead:

1. exact bootstrap text is validated in the active composer immediately before the click;
2. the content script writes a submitted claim bound to the exact transaction, child-request digest and bootstrap digest;
3. the claimed tab is observed entering a supported provisional route;
4. the same claimed tab reaches one canonical `/c/<id>` route;
5. the canonical child contains exactly one user turn;
6. durable registration and `SpawnTransaction=done` bind that child to the exact admitted request.

The regression suite retains exact-DOM paths where available, but Stage 8 no longer depends on expanded long-message DOM text.

## Safety invariants retained

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- Chat Bridge remains a bounded browser actuator.
- `local-agent` remains `execution_enabled=false` for the reasoning-child slice.
- child chats never receive independent Mac/task execution authority.
- no production Chrome/profile mutation.
- no Native Messaging control plane.
- no blind replay after any potentially submitted ambiguous browser effect.
- one proof has at most one browser spawn attempt.

The earlier ambiguous proofs remain recovery evidence. They must never be replayed.

## Next milestone — checkpoint and terminal recording

The next milestone is not another spawn campaign. Stage 8 has already proven automatic child creation.

Implement the smallest durable lifecycle slice for an already registered active child:

```text
active
  -> terminal_pending_evidence
  -> terminal_recorded
```

Before implementation, audit the existing conversation contracts/store/tests and define the minimum bounded terminal/checkpoint evidence model. Preserve the current lifecycle invariants and make the evidence content-addressed or otherwise immutably bound to the exact child request and registration.

Required properties for the next slice:

- an active child cannot become `terminal_recorded` without durable terminal evidence;
- evidence must bind to the exact child request digest and canonical child registration;
- terminal recording must be idempotent for identical evidence and fail closed on conflicting evidence;
- terminal state transitions must remain serialized by the existing workflow execution lock;
- no adoption/retirement semantics are introduced yet;
- no new browser effect is required until the deterministic storage/state contract is implemented and tested;
- restart/recovery behavior across external-effect boundaries remains a later milestone.

## Exact continuation sequence

1. Fetch fresh `develop/conversation-fabric` and production `main`; require production to remain unchanged unless an explicit release decision occurred.
2. Verify `/Users/michal/local-agent-dev` is clean and contains the accepted code checkpoint plus any intentional documentation-only commits.
3. Audit `local_agent/conversation/contract.py`, `state.py`, `store.py`, existing workflow evidence patterns and `tests/test_conversation_store.py` before changing behavior.
4. Write the terminal/checkpoint record contract and positive/negative tests first or in the same bounded implementation slice.
5. Run focused conversation/workflow tests on Mac through `host-ops`.
6. Run the normal bridge/repository verification required by the actual diff.
7. Push one reviewed checkpoint to `develop/conversation-fabric` and establish exact-SHA CI before any live terminal lifecycle proof.
8. Only after checkpoint/terminal recording is complete may work advance to adoption and retirement.

## Out of scope now

Do not start yet:

- adoption or retirement;
- multi-child fan-out;
- fleet scheduling;
- rollover;
- broad Superchat automation;
- automatic scheduling beyond the proven single-child lifecycle;
- production release/merge without a separate explicit release decision.

## Operating rules

- Use direct GitHub operations for repository inspection and repository-side changes.
- Use `host-ops` for every Mac-local operation: checkout updates, tests, browser/profile inspection and live proof execution.
- Never mutate production `main`, `chat-bridge-state`, `operator-control` or archive branches as part of Conversation Fabric development.
- Never use, copy or inspect raw authentication secrets from the production Chrome profile.
- Keep machine-generated source, comments, tests, documentation, prompts, task metadata, logs and commit messages English-only.

## Recovery rule

If a future conversation is unsure where to continue, use this handoff plus `docs/conversation_fabric/CURRENT_PLAN.md` as the checkpoint tie-breaker, then verify every mutable fact against GitHub and `host-ops` before effects.
