# Local Agent development plan

Status: Conversation Fabric end-to-end MVP and operator-visible GitHub intake are accepted in development. The next product milestone is a controlled production rollout/release decision.

## Stable production baseline

Production remains Local Agent v4.19.12 / Chat Bridge 0.6.2 on:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`

Conversation Fabric development must not mutate production `main` or the production Chrome profile without a separate explicit release decision.

## Product direction

```text
User
  -> Operator Chat / Superchat
    -> GitHub durable control/evidence
      -> Local Agent deterministic orchestration
        -> host-ops deterministic host effects
        -> narrow ChatGPT browser actuator for child lifecycle
      -> durable result/evidence
    -> Operator Chat synthesis
```

Permanent boundaries:

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- ChatGPT conversations remain the reasoning layer.
- Chat Bridge is a narrow browser transport/actuator, not workflow authority.
- Child chats have no independent machine authority.
- No direct OpenAI API model loop.
- No MCP or Native Messaging control plane for Conversation Fabric.

## Branch roles

| Branch | Role |
| --- | --- |
| `main` | production runtime/source of truth |
| `develop/conversation-fabric` | canonical Conversation Fabric development line |
| `work/conversation-*` / `work/stage8-*` | temporary bounded candidate branches only |
| `chat-bridge-state` | operational desired state, not development |
| `operator-control` | global operator safety/control, not development |

## Accepted development checkpoint

- operator-visible CODE: `37e480d3b36a5c15db89c944ef46f01225a4b379`
- commit: `Add operator-visible Conversation Fabric intake`
- tree: `02910eadc544a87cd9fcb5287abd26e1a05d7688`
- exact-SHA clean CI: `37085317848`, all five jobs passed
- final clean operator proof result: `OPERATOR_CLEAN_FINAL_OK 37e480d3b36a5c15db89c944ef46f01225a4b379`
- final clean child: `https://chatgpt.com/c/6ac057fc-b140-83ed-b74f-61f1b8de94d7`
- underlying accepted end-to-end MVP: `93494b2a99162eef5bcf44caae087b71459233b4`, CI `37076387941`
- production remained unchanged

Documentation-only commits may advance the canonical branch; always distinguish accepted CODE from a later docs-only head.

## Completed Conversation Fabric milestones

1. Stage 8 automatic child creation/identity proof — `93fb65204db03c54d0080803d26266f3c06d777e`, CI `37022787748`.
2. Durable terminal records — `a16918d32bc366dbc9d8a8793669baa214d13620`, CI `37036591713`.
3. Durable adoption/retirement — `e76dc4a114f750cc0beabdbb2ad626d41ff2e986`, CI `37054505079`.
4. Restart/recovery boundary proofs — `2557f9477ff34ebb5b8502a15747e5d78f29bd5a`, CI `37056289262`.
5. First-class manual child lifecycle — `78f72819c2e7d60e0cae4599f8c24976cb0ce2a4`, CI `37062617205`.
6. End-to-end MVP — `93494b2a99162eef5bcf44caae087b71459233b4`, CI `37076387941`.
7. Operator-visible GitHub request/result intake — `37e480d3b36a5c15db89c944ef46f01225a4b379`, CI `37085317848`.

## Accepted operator contract

- request path: `.agent/conversation/requests/<request-id>.json`;
- result path: `.agent/conversation/results/<request-id>.json`;
- bounded one-to-four child operator intent;
- immutable request identity and fail-closed same-ID conflicts;
- existing MVP lifecycle remains semantic owner;
- local durable result spool with fresh-origin publication proof before deletion;
- default-disabled supervisor intake and explicit runtime configuration;
- no changes to `.agent/tasks` semantics.

## Current milestone: controlled production rollout/release

Do not create another hidden lifecycle or intake milestone. Inspect current release mechanics, choose the exact release candidate/configuration, preserve default-disabled rollout until the code is installed and verified, and require explicit user approval before production mutation.

After any controlled release, improve operator progress/diagnostics only from real use. Broad automatic scheduling/rollover and fleet management remain later product milestones.

## Verification discipline

For every non-trivial runtime change:

1. fetch fresh canonical and production state;
2. verify DEV and production cleanliness;
3. identify a concrete product/reliability gap before coding;
4. make the smallest bounded change;
5. add focused tests for the affected contract;
6. use live browser evidence only for changed external-effect boundaries;
7. use `host-ops` for Mac-local operations and direct GitHub operations for repository-side work;
8. establish exact-SHA CI before accepting another CODE checkpoint;
9. advance only `develop/conversation-fabric` after validation;
10. update durable docs after acceptance.
