# Conversation Fabric — current execution plan

Status: parent Superchat self-diagnostic completed. Core Local Agent 4.20.5 execution/scheduler/routing safety is healthy. The only active functional repair track is child-browser delegation readiness.

## Baseline

- released/tagged runtime commit: `v4.20.5` = `bd793d60c3bce4b247deb80a7e2bfc88e8bf4373`;
- Local Agent release/runtime version = 4.20.5;
- Chat Bridge release source = 0.8.1;
- production completed natural self-update to the exact release commit;
- release CI was 5/5 green;
- current `main` may include later verified documentation-only maintenance and must not be equated automatically with the installed runtime revision;
- old parent `chat-7781d9b9` has been disabled;
- Conversation Operator intake remains default-disabled and is not enabled by the current production LaunchAgent configuration.

## Permanent architecture

```text
Parent Superchat
  -> decomposes/coordinates reasoning work
  -> GitHub durable control/evidence
  -> optional bounded child reasoning chats
  -> direct GitHub edits or exact target .agent/tasks
  -> verifies results and synthesizes decisions
```

Rules:

- Chat Bridge conversation identity is transport/scheduling only.
- Repository names in the active goal or durable request are reasoning context and may include donor + target repositories without Rebind.
- Child chats are reasoning-only and have no independent machine execution authority.
- `.agent/tasks` remains the only executable repository-work contract.
- Every executable task uses the actual target repository's exact canonical `agent_binding` and normal registry/control/task admission.
- GitHub is the durable control/evidence plane; DOM state is only browser transport evidence.
- `local-agent` remains execution-disabled in the runtime catalog.

## Self-diagnostic verdict

The 2026-10-04 parent-led audit found no P0/P1 regression in scheduler/control, target routing/bindings, process lifecycle/resources or transport-only parent coordination.

The detailed durable evidence is in `SELF_DIAGNOSTIC_2026-10-04.md`.

## Active child-browser repair

The current MVP child backend still depends on the isolated browser actuator. The prior live pilot failed before child registration with `chatgpt_login_timeout`.

Root cause isolated by the self-diagnostic: `waitForLoginReady()` only probed authenticated session state after composer DOM visibility. A valid authenticated session with delayed/changed composer DOM could therefore be mislabeled as a login timeout.

Draft PR #135 fixes only that coupling and adds a delayed-composer regression test. It has been rebased/cleaned to one commit directly on the current post-doc-cleanup `main`:

`ba884c206925e6e25041657a0250a9459e3aa8f2`

Fresh CI on that exact head is 5/5 green, including `bridge-browser` and `macos-smoke`.

## Next acceptance sequence

Do not broaden scope before this sequence is complete:

1. review PR #135 as the only code repair candidate;
2. make an explicit merge/deploy decision;
3. after deployment, verify exact installed revision from fresh status;
4. run one bounded child pilot;
5. if and only if that pilot succeeds, decide whether to configure Conversation Operator intake for real parent fan-out;
6. add normal diagnostics for Conversation Operator enabled/configured state before relying on it operationally.

Do not repeat the historical manual Chrome login / Cloudflare / DOM-proof loop. If the bounded pilot still fails, capture the exact new failure and continue from that evidence.

## Deferred maintenance

Keep these separate from the child repair:

- large Growclip/BloomML worktrees and storage hygiene;
- `hardware-lab` sparse/partial-clone policy drift;
- operator observability improvements;
- broad fleet scheduling, automatic rollover and large fan-out.
