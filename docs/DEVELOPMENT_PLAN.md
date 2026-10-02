# Local Agent development plan

Status: Conversation Fabric end-to-end MVP is accepted in development. The next product milestone is operator-visible integration and a controlled release decision.

## Stable production baseline

Production remains Local Agent v4.19.12 / Chat Bridge 0.6.2 on:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`

Conversation Fabric development must not mutate production `main` or the production Chrome profile without a separate explicit release decision.

## Product direction

The target remains one user-visible Local Agent product centered on one long-lived Operator Chat / Superchat:

```text
User
  -> Operator Chat / Superchat
    -> GitHub durable control/evidence
      -> Local Agent deterministic orchestration
        -> host-ops deterministic Mac/host effects
        -> narrow ChatGPT browser actuator for child-chat lifecycle
      -> durable result/evidence
    -> Operator Chat synthesis
```

Permanent boundaries:

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- ChatGPT conversations remain the reasoning layer.
- Chat Bridge is a narrow browser transport/actuator, not workflow authority.
- Browser DOM state is transport evidence, not durable scheduler state.
- Child chats have no independent machine authority.
- `local-agent` remains `execution_enabled=false` for reasoning-child browser work.
- No direct OpenAI API model loop.
- No Native Messaging control plane for this architecture.

## Branch roles

| Branch | Role |
| --- | --- |
| `main` | production runtime/source of truth |
| `develop/conversation-fabric` | canonical Conversation Fabric development line |
| `work/conversation-*` / `work/stage8-*` | temporary bounded candidate branches only |
| `chat-bridge-state` | operational desired state, not development |
| `operator-control` | global operator safety/control, not development |

## Accepted development checkpoint

- CODE: `93494b2a99162eef5bcf44caae087b71459233b4`
- commit: `Add end-to-end Conversation Fabric MVP`
- tree: `c4354951c4b4af9c558ce8adc59d2118f51f8146`
- exact-SHA CI: `37076387941`
- all five CI jobs passed
- final clean live canary: `mvp-clean-final-canary-v1`
- final child: `https://chatgpt.com/c/6ac03b3b-cc70-83eb-8f75-09fcbf277733`
- final child state: `retired`
- final workflow state: `completed`
- production remained unchanged

Documentation-only commits may advance the canonical branch; always distinguish the accepted CODE checkpoint from a later docs-only head.

## Completed Conversation Fabric milestones

1. Stage 8 automatic child creation/identity proof — `93fb65204db03c54d0080803d26266f3c06d777e`, CI `37022787748`.
2. Durable terminal records — `a16918d32bc366dbc9d8a8793669baa214d13620`, CI `37036591713`.
3. Durable adoption/retirement — `e76dc4a114f750cc0beabdbb2ad626d41ff2e986`, CI `37054505079`.
4. Restart/recovery boundary proofs — `2557f9477ff34ebb5b8502a15747e5d78f29bd5a`, CI `37056289262`.
5. First-class manual child lifecycle — `78f72819c2e7d60e0cae4599f8c24976cb0ce2a4`, CI `37062617205`.
6. End-to-end MVP with bounded multi-child delegation, result capture, retirement and exact owned-tab cleanup — `93494b2a99162eef5bcf44caae087b71459233b4`, CI `37076387941`.

The accepted MVP includes recovery for ambiguous/restarted browser effects, collapsed/bootstrap identity, transient provisional routes, observer stalls and ownership-safe child cleanup. The MVP was used to delegate real review tasks during its own development; review findings were fixed before the final accepted checkpoint.

## Current milestone: operator-visible integration / release decision

Do not create another lifecycle milestone just to continue backend work.

The next implementation work should answer a product question: how does the long-lived Operator Chat invoke the accepted capability with minimal friction and see progress/results clearly?

The smallest useful slice should:

- expose or wrap the accepted MVP rather than duplicate it;
- show bounded per-child progress/results to the operator;
- preserve GitHub/Local Agent as durable authority;
- keep Chat Bridge as a narrow effect layer;
- reuse the MVP itself for bounded delegated review when useful;
- avoid broad fleet scheduling, rollover or autonomous task discovery.

Once that operator-facing slice is clear, decide whether to release the accepted capability to production. A production release requires a separate explicit decision and the repository's version/changelog/release process.

## Later product milestones

After operator-visible MVP integration and any controlled release:

1. normalize the persistent DEV browser profile into a reusable root-independent location if still beneficial;
2. improve operator progress/diagnostics based on real use;
3. add Superchat fleet/control features only when bounded MVP usage demonstrates the need;
4. add broader automatic scheduling/rollover only after product requirements and safety contracts are explicit.

## Verification discipline

For every non-trivial runtime change:

1. fetch fresh canonical and production state;
2. verify DEV and production cleanliness;
3. identify a concrete product/reliability gap before coding;
4. make the smallest bounded change;
5. add focused tests for the affected contract;
6. use live browser evidence only for changed browser-effect boundaries;
7. use `host-ops` for Mac-local operations and direct GitHub operations for repository-side work;
8. establish exact-SHA CI before accepting another CODE checkpoint;
9. advance only `develop/conversation-fabric` after validation;
10. update durable docs after acceptance.

Exact GitHub state and durable local evidence outrank remembered chat context.
