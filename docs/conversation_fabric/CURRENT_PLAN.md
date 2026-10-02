# Conversation Fabric — current execution plan

Status: the end-to-end Conversation Fabric MVP is accepted on the canonical development line. The current priority is operator-visible integration or a controlled production release decision, not another hidden lifecycle milestone.

## Current baseline

Production remains unchanged:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent v4.19.12
- Chat Bridge 0.6.2
- production checkout: `/Users/michal/local-agent`

Canonical development line:

- branch: `develop/conversation-fabric`
- accepted CODE checkpoint: `93494b2a99162eef5bcf44caae087b71459233b4`
- accepted commit: `Add end-to-end Conversation Fabric MVP`
- exact-SHA CI: `37076387941`
- all five jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`
- DEV checkout: `/Users/michal/local-agent-dev`

Documentation-only commits may advance the canonical branch beyond the accepted CODE checkpoint. Runtime/effect work must always identify the accepted CODE SHA separately from the current docs head.

## What is complete

The following lifecycle milestones are closed:

- automatic one-child spawn/identity proof;
- durable terminal recording;
- durable adoption and retirement;
- restart/recovery boundary proofs;
- first-class manual lifecycle parity;
- complete DEV MVP child orchestration, result collection and exact owned-tab cleanup;
- bounded multi-child delegation used for real review work.

The accepted MVP path is:

```text
request
  -> spawn
  -> exact bootstrap
  -> canonical identity
  -> registration
  -> active
  -> result observation
  -> durable result evidence
  -> terminal
  -> adoption
  -> succeeded reasoning node
  -> retired
  -> exact owned-tab close
```

Recovery/fail-closed behavior includes:

- strict create/pre-submit recovery;
- no blind replay after ambiguous submit;
- exact transient-route ownership evidence;
- collapsed-turn exact identity handling;
- bounded observer-session retry;
- manual attach for an already-created ambiguous child;
- safe abandonment of an unrecoverable ambiguous child while preserving the original ambiguous spawn and forbidding replacement;
- restart-safe terminal/adoption/retirement ordering;
- observer/close cache bound to exact child ownership identity, not URL alone.

## Acceptance evidence

Accepted CODE:

- `93494b2a99162eef5bcf44caae087b71459233b4`
- tree: `c4354951c4b4af9c558ce8adc59d2118f51f8146`
- exact-SHA CI run: `37076387941`, 5/5 green

Final clean live canary:

- workflow: `mvp-clean-final-canary-v1`
- request: `mvp-clean-final-child-001`
- canonical child: `https://chatgpt.com/c/6ac03b3b-cc70-83eb-8f75-09fcbf277733`
- child state: `retired`
- workflow state: `completed`
- terminal record: present
- adoption record: present
- result: `MVP_CLEAN_FINAL_OK` plus exact accepted SHA
- failures: none

The MVP was also used to delegate its own bounded lifecycle and browser reviews. Findings from those child reviews were fixed before the accepted clean checkpoint.

## Permanent architecture boundaries

- GitHub is the durable control/evidence plane.
- Local Agent is deterministic orchestration and remains model-free.
- ChatGPT conversations are the reasoning layer.
- Chat Bridge is a bounded browser transport/actuator, not durable workflow authority.
- Browser DOM state is transport evidence, not scheduler state.
- Child chats have no independent machine execution authority.
- `local-agent` remains `execution_enabled=false` for reasoning-child browser work.
- No blind replay after a potentially submitted browser effect.
- No production Chrome-profile mutation.
- No second scheduler or Native Messaging control plane.

## Current product milestone

The next work should make the accepted capability visible/useful rather than adding more hidden lifecycle machinery.

Preferred order:

1. define the smallest operator-facing entrypoint from the intended long-lived Operator Chat / Superchat into the accepted MVP;
2. use the MVP itself for bounded child delegation while implementing/reviewing that work;
3. decide whether the accepted checkpoint is ready for a controlled production release;
4. if releasing, perform the repository's normal version/changelog/release validation, exact-SHA CI and production rollout discipline;
5. only add more lifecycle/browser hardening when a concrete defect from real use requires it.

Production `main` must remain untouched until an explicit release decision is made.

## Bounded delegation policy

The MVP may be used in DEV for up to a small bounded set of independent reasoning/review children. Spawn effects remain serialized; child reasoning and result collection can overlap.

This is not yet a general fleet scheduler. Broad autonomous scheduling, rollover, fleet management and large fan-out remain later product work and should not be introduced merely to expand scope.

## Verification discipline

For future runtime changes:

1. start from the accepted canonical CODE checkpoint, distinguishing later docs-only heads;
2. identify the concrete user-visible or reliability gap first;
3. make the smallest bounded change;
4. add focused positive/negative/idempotency/restart tests appropriate to the boundary;
5. use real browser evidence only where the changed boundary crosses a browser effect;
6. run Mac-local checks through `host-ops`;
7. establish exact-SHA CI before accepting another CODE checkpoint;
8. update durable handoff docs only after acceptance.

For operational continuation, use `docs/CURRENT_HANDOFF.md`. A ready-to-paste continuation prompt is maintained in `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`.
