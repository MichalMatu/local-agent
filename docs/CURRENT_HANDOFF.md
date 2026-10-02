# Current handoff — Conversation Fabric end-to-end MVP accepted

Date: 2026-10-03
Status: manual lifecycle parity and the end-to-end Conversation Fabric MVP are complete on the canonical development line. The next decision is operator-visible integration / controlled release, not another hidden lifecycle-hardening milestone.

## Read this first

Repository state, durable docs and fresh `host-ops` evidence outrank chat memory.

Read in this order:

1. `AGENTS.md`
2. this file
3. `docs/conversation_fabric/CURRENT_PLAN.md`
4. `docs/DEVELOPMENT_PLAN.md`
5. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

## Authoritative repository state

Production remains unchanged and clean:

- `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent: v4.19.12
- Chat Bridge: 0.6.2
- production checkout: `/Users/michal/local-agent`
- production Chrome profile remains protected: `/Users/michal/Library/Application Support/Google/Chrome`

Conversation Fabric development:

- canonical branch: `develop/conversation-fabric`
- accepted CODE checkpoint: `93494b2a99162eef5bcf44caae087b71459233b4`
- accepted commit: `Add end-to-end Conversation Fabric MVP`
- exact-SHA CI run: `37076387941`
- CI result: all five jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`
- DEV checkout: `/Users/michal/local-agent-dev`

Documentation-only commits may advance `develop/conversation-fabric` beyond the accepted CODE checkpoint. Always distinguish accepted CODE `93494b2...` from a later docs-only head before making runtime effects.

## Accepted MVP

The DEV MVP now performs the complete bounded child lifecycle:

```text
ChildRequest
  -> durable spawn intent
  -> owned ChatGPT child tab
  -> exact bootstrap submit
  -> canonical child identity
  -> ChildRegistration
  -> active
  -> bounded assistant-result observation
  -> durable result evidence
  -> terminal_pending_evidence
  -> terminal_recorded
  -> durable adoption
  -> workflow reasoning node succeeded
  -> retired
  -> close exact owned child tab
```

It also supports bounded multi-child delegation. Browser spawning remains globally serialized for safety, while registered children can reason concurrently and the parent can collect their results in one campaign.

Accepted recovery/safety properties include:

- no blind resubmit after a potentially submitted browser effect;
- lost create/submit acknowledgement recovery and restart reconciliation;
- transient provisional-route evidence bound to the exact claimed spawn tab/transaction;
- exact/bootstrap-bound child identity, including collapsed user turns;
- one bounded observer-session retry after transport stall;
- terminal/adoption/retirement restart recovery;
- first-class fresh manual lifecycle path;
- ambiguous manual attach recovery without resubmit;
- explicit unrecoverable ambiguity abandonment that preserves the original `ambiguous` transaction and never authorizes replacement;
- child observer/close ownership bound to exact transaction/request/bootstrap identity rather than URL alone.

Chat Bridge remains a bounded browser actuator. Durable workflow authority remains in Local Agent/GitHub state.

## Final clean acceptance proof

Final clean canary:

- workflow: `mvp-clean-final-canary-v1`
- request: `mvp-clean-final-child-001`
- request digest: `sha256:3bfdcf5a72c6f9b8094f74d6d9bb72609d1ce46fb5168cac4b9b1a7473153e91`
- canonical child: `https://chatgpt.com/c/6ac03b3b-cc70-83eb-8f75-09fcbf277733`
- accepted code in the child bootstrap/result: `93494b2a99162eef5bcf44caae087b71459233b4`
- child state: `retired`
- workflow state: `completed`
- result text: `MVP_CLEAN_FINAL_OK` plus the exact accepted SHA
- durable terminal record: present
- durable adoption record: present
- failures: none
- production mutation: none

The same MVP was also used during development to delegate real review tasks to child chats. Those reviews found lifecycle/browser defects, the defects were fixed, and the final accepted tree was reverified by focused tests, exact-SHA CI and the clean live canary above.

## Completed milestone ledger

- Stage 8 automatic child proof: `93fb65204db03c54d0080803d26266f3c06d777e`, CI `37022787748`
- durable terminal records: `a16918d32bc366dbc9d8a8793669baa214d13620`, CI `37036591713`
- durable adoption/retirement: `e76dc4a114f750cc0beabdbb2ad626d41ff2e986`, CI `37054505079`
- restart/recovery boundary proofs: `2557f9477ff34ebb5b8502a15747e5d78f29bd5a`, CI `37056289262`
- first-class manual child lifecycle: `78f72819c2e7d60e0cae4599f8c24976cb0ce2a4`, CI `37062617205`
- end-to-end Conversation Fabric MVP: `93494b2a99162eef5bcf44caae087b71459233b4`, CI `37076387941`

Stage 8 remains closed; do not rerun its historical acceptance campaign.

## Current priority

Do not start another abstract backend/lifecycle milestone merely because one is available.

The next useful product step is one of:

1. make the accepted MVP directly operator-visible and convenient from the intended Superchat/operator workflow; or
2. prepare a controlled release from the accepted development checkpoint to production, with version/changelog/release validation and an explicit release decision.

Until a release decision is made, production `main` stays unchanged.

For new DEV work, prefer using the accepted MVP itself to delegate bounded, independent reasoning/review tasks to child chats when that materially shortens the work. Do not treat this bounded delegation as a general fleet scheduler: rollover, broad autonomous scheduling and fleet management are still later product work.

## Continuation sequence

1. Fetch fresh `main`, `develop/conversation-fabric`, `host-ops:agent-control` and daemon state.
2. Verify the accepted CODE checkpoint and distinguish any later docs-only head.
3. Verify DEV and production checkouts are clean and production is still `979ef080...`.
4. Do not repeat the already accepted MVP proof unless runtime code changes require a new acceptance proof.
5. Use the MVP for bounded child delegation during further DEV work where useful.
6. Prioritize an operator-visible integration or a controlled release plan before adding more backend layers.
7. If runtime behavior changes, add focused regression tests and require exact-SHA CI plus only the live proof needed by the changed external-effect boundary.

## Non-negotiable invariants

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- ChatGPT conversations remain the reasoning layer.
- Chat Bridge remains a bounded browser actuator, not workflow authority.
- child chats do not receive independent machine execution authority.
- browser DOM is transport evidence, not durable scheduler state.
- no blind replay after a potentially submitted ambiguous effect.
- no production Chrome-profile mutation.
- no production `main` mutation without a separate explicit release decision.
- do not use `chat-bridge-state` or `operator-control` as development branches.
- machine-generated source, tests, docs, prompts, task metadata, logs and commit messages remain English-only.
