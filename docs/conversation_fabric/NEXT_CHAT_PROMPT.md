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

Current durable runtime baseline:

- production `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent 4.19.12 / Chat Bridge 0.6.2
- canonical development branch: `develop/conversation-fabric`
- accepted CODE checkpoint: `a16918d32bc366dbc9d8a8793669baa214d13620`
- accepted code commit: `Add durable child terminal records`
- exact-SHA canonical CI run: `37036591713`
- all five jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`

Documentation-only commits may advance the canonical branch beyond the accepted CODE checkpoint. Fetch the fresh head and distinguish docs-only commits from runtime changes before effects.

Stage 8 automatic one-child proof is COMPLETE and remains closed.

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
- bounded completion evidence: present and matching
- manual attach/recovery: not used
- production mutation: none

Do NOT start another Stage 8 spawn campaign or create another child for that milestone.

The terminal/checkpoint milestone is also COMPLETE on accepted CODE checkpoint `a16918d32bc366dbc9d8a8793669baa214d13620`.

Accepted lifecycle path:

```text
active
  -> terminal_pending_evidence
  -> terminal_recorded
```

Accepted terminal-record properties:

- `active -> terminal_pending_evidence` is explicit and durable;
- `terminal_recorded` is impossible without valid durable terminal evidence;
- evidence binds the exact child request ID/digest, canonical durable `ChildRegistration` digest and canonical child URL;
- evidence and evidence references are bounded and schema-validated;
- identical semantic recording is idempotent;
- conflicting evidence fails closed;
- writes use the existing workflow execution lock;
- evidence is persisted before terminal state, making an interrupted state write restart-recoverable;
- persisted evidence/state relationships are revalidated on reload/restart;
- focused tests cover missing registration/evidence, conflict, invalid ordering, exact binding, idempotency, bounds, crash recovery and lock reuse;
- no adoption/retirement behavior and no browser effect were added by this slice.

Implementation surfaces to re-open before later lifecycle work:

- `local_agent/conversation/terminal.py`
- `local_agent/conversation/state.py`
- `local_agent/conversation/store.py`
- `tests/test_conversation_terminal.py`
- relevant workflow state/store/revision surfaces discovered by the next audit

The next milestone is adoption and retirement.

There is no accepted implementation design for adoption/retirement yet. Do not infer it from old chats and do not blindly extend the terminal design.

First perform one bounded read-only preimplementation audit on the fresh accepted repository state. The audit must establish from current code:

- where adoption and retirement already appear or are consumed;
- the smallest durable preconditions/evidence needed for each transition;
- legal ordering and fail-closed behavior;
- idempotency/conflict semantics;
- restart/reload validation requirements;
- locking and atomic-write boundaries;
- whether any browser effect is actually required.

Persist the audit result through `host-ops`. Do not mutate source during the audit.

If the audit supports a small implementation slice, continue autonomously with that smallest bounded slice: add focused positive/negative/idempotency/restart tests, implement only the audited contract, verify locally through `host-ops`, push one reviewed CODE checkpoint to `develop/conversation-fabric`, close exact-SHA CI, and only then update durable docs.

Use direct GitHub operations for repository-side inspection/changes. Use `host-ops` for every Mac-local checkout, synchronization, test or process operation.

Do not touch:

- production `main` without a separate explicit release decision;
- `chat-bridge-state`;
- `operator-control`;
- production Chrome profile `/Users/michal/Library/Application Support/Google/Chrome`.

Preserved Stage 8 isolated profile/root remain evidence only unless a later audited boundary explicitly needs browser work:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- persistent profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`

Do not broaden this milestone into restart/recovery campaigns across unrelated external effects, manual lifecycle parity, Browser Driver promotion, multi-child fan-out, fleet scheduling, rollover or broad Superchat automation.

First perform a short read-only preflight and report whether the adoption/retirement audit is safe to continue. If safe, continue autonomously with the bounded read-only audit, then with the smallest implementation slice only if the audit establishes one clearly.
