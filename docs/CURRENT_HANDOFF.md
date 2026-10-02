# Current handoff — Conversation Fabric after terminal recording

Date: 2026-10-02
Status: Stage 8 automatic one-child proof completed; durable terminal/checkpoint recording completed; adoption and retirement are next.

## Read this first

This file is the authoritative operational continuation point for Conversation Fabric work. Do not reconstruct current state from older chat history.

Then read:

1. `AGENTS.md`
2. `docs/conversation_fabric/CURRENT_PLAN.md`
3. `docs/DEVELOPMENT_PLAN.md`
4. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

Exact GitHub state and durable `host-ops` evidence outrank remembered chat context or browser appearance.

## Repository state

Production remains unchanged:

- `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent: v4.19.12
- Chat Bridge: 0.6.2

Conversation Fabric development:

- canonical branch: `develop/conversation-fabric`
- accepted CODE checkpoint: `a16918d32bc366dbc9d8a8793669baa214d13620`
- accepted commit: `Add durable child terminal records`
- exact-SHA GitHub Actions run on canonical branch: `37036591713`
- all jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`
- an earlier isolated-candidate run for the same exact SHA also passed: `37035403791`
- Mac DEV checkout: `/Users/michal/local-agent-dev`
- production checkout: `/Users/michal/local-agent`

Documentation-only commits may advance `develop/conversation-fabric` beyond the accepted CODE checkpoint. Always distinguish the accepted runtime CODE SHA above from a later documentation-only branch head before effects.

The isolated Stage 8 live root/profile remains preserved for evidence:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- persistent isolated profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`
- production Chrome profile must never be used or copied: `/Users/michal/Library/Application Support/Google/Chrome`

## Stage 8 completion remains closed

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
- durable child lifecycle at proof completion: `active`
- matching durable `ChildRegistration`: present
- bounded completion evidence: present and matching
- manual attach/recovery: not used
- production `main`: unchanged

Do not start another Stage 8 spawn campaign. Automatic one-child creation is already proven.

## Completed milestone — checkpoint and terminal recording

Accepted CODE checkpoint `a16918d32bc366dbc9d8a8793669baa214d13620` implements the deterministic lifecycle slice:

```text
active
  -> terminal_pending_evidence
  -> terminal_recorded
```

Implementation surfaces:

- `local_agent/conversation/terminal.py`
- `local_agent/conversation/store.py`
- `tests/test_conversation_terminal.py`

The accepted contract is intentionally small:

- terminal evidence is a separate bounded schema-validated durable record;
- it binds the exact child request ID/digest, the digest of the canonical durable `ChildRegistration`, and the canonical child URL;
- `evidence_refs` must be a non-empty bounded list of canonical kind/id/sha256 references;
- an active child must explicitly enter `terminal_pending_evidence` before terminal evidence can be recorded;
- `terminal_recorded` cannot be reached without a valid durable terminal record;
- terminal evidence is atomically written before the terminal lifecycle state, so a crash between those writes leaves a recoverable pending state rather than an unsupported terminal state;
- a semantically identical retry is idempotent and returns the existing durable record; conflicting evidence fails closed;
- mutations use the existing workflow execution lock;
- reload/restart validation revalidates request, registration, terminal evidence and lifecycle consistency;
- no adoption/retirement behavior and no browser effect were added in this slice.

Focused tests cover positive persistence/reload, missing registration, missing evidence, conflicting evidence, invalid ordering, exact request/registration binding, bounded schema validation, idempotency, crash recovery between evidence/state writes, reload fail-closed behavior and lock reuse.

## Verification ledger for terminal recording

Read-only preimplementation audit:

- task/result: `conversation-terminal-evidence-preimplementation-audit-20261002-v1`
- status: `done`
- audited code: `93fb65204db03c54d0080803d26266f3c06d777e`
- no repository mutation

The earlier malformed implementation task remains non-authoritative:

- task/result: `conversation-terminal-record-implementation-20261002-v1`
- status: `failed`
- failure: `invalid_task_file`
- `started_at=null`
- no commands ran

Accepted candidate/local verification:

- CODE SHA: `a16918d32bc366dbc9d8a8793669baa214d13620`
- focused conversation suite through `host-ops`: 38 tests passed
- Python compile: passed
- Ruff: passed
- `git diff --check`: passed
- DEV checkout was clean after verification and was synchronized to the accepted CODE SHA
- production checkout remained clean at `979ef080ddb69d6e18aaf81510e3175bac2f33d2`

One broad local verifier attempt inherited an internal closed `LOCAL_AGENT_LEASE_FDS` descriptor from the `host-ops` worker; after sanitizing that environment, the relevant compile/lint/focused checks passed. The local `macos-smoke` profile then exposed only missing local `mcp`/`httpx2` dependencies. Canonical exact-SHA CI is authoritative and passed its complete `macos-smoke` job together with the other four jobs.

## Current milestone — adoption and retirement

Adoption and retirement are now the next ordered milestone. No accepted implementation contract for that milestone has been established yet.

Do not infer semantics from old chats. Start with a fresh read-only preimplementation audit of the accepted CODE checkpoint and current durable workflow/conversation contracts before changing behavior.

At minimum, the audit should re-open the lifecycle/store surfaces that now enforce terminal recording, identify every existing meaning or consumer of adoption/retirement, determine the smallest durable state/evidence contract needed, and identify restart/idempotency/fail-closed requirements before implementation.

Do not add browser effects unless the audited adoption/retirement boundary actually requires one. Do not expand into multi-child fan-out, scheduling, rollover or Superchat fleet behavior.

## Exact continuation sequence

1. Fetch fresh `main`, `develop/conversation-fabric`, `host-ops:agent-control` and `.agent/status/daemon.json`.
2. Verify `/Users/michal/local-agent-dev` is clean and identify the accepted CODE checkpoint versus any later docs-only head.
3. Verify production `/Users/michal/local-agent` remains clean at the production baseline.
4. Re-read this handoff, `CURRENT_PLAN.md` and `DEVELOPMENT_PLAN.md`.
5. Re-open the accepted terminal-record implementation and tests before reasoning about later lifecycle states.
6. Perform one bounded read-only preimplementation audit for adoption and retirement; record the result durably through `host-ops`.
7. Derive the smallest next contract from repository state plus that audit; do not invent or import semantics from chat memory.
8. Only then implement one bounded slice with positive/negative/idempotency/restart tests appropriate to the audited design.
9. Use direct GitHub operations for repository-side changes and `host-ops` for every Mac-local checkout/test operation.
10. Establish exact-SHA CI before accepting the next CODE checkpoint.
11. Update durable handoff docs only after the next CODE checkpoint is accepted.

## Safety invariants retained

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- Chat Bridge remains a bounded browser actuator.
- `local-agent` remains `execution_enabled=false` for reasoning-child browser work.
- child chats never receive independent Mac/task execution authority.
- no production Chrome/profile mutation.
- no Native Messaging control plane.
- no blind replay after any potentially submitted ambiguous browser effect.
- never mutate production `main`, `chat-bridge-state` or `operator-control` as part of Conversation Fabric development.
- machine-generated source, comments, tests, documentation, prompts, task metadata, logs and commit messages remain English-only.

## Out of scope now

Do not start yet:

- restart/recovery proof across every external-effect boundary beyond what is needed by the bounded next slice;
- manual lifecycle parity;
- Browser Driver promotion;
- multi-child fan-out;
- fleet scheduling;
- rollover;
- broad Superchat automation;
- production release/merge without a separate explicit release decision.

## Next-chat bootstrap

A ready-to-paste continuation prompt is maintained at:

- `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

If a future conversation is unsure where to continue, use this handoff plus `docs/conversation_fabric/CURRENT_PLAN.md` as the checkpoint tie-breaker, then verify every mutable fact against GitHub and `host-ops` before effects.
