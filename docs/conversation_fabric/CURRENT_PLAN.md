# Conversation Fabric — current execution plan

Status: parent Superchat self-diagnostic completed. Core Local Agent 4.20.5 execution/scheduler/routing safety is healthy. The only active functional repair track is child-browser delegation readiness.

## Baseline

- `main` / `v4.20.5` = `bd793d60c3bce4b247deb80a7e2bfc88e8bf4373`;
- Local Agent source/runtime = 4.20.5;
- Chat Bridge source = 0.8.1;
- production completed natural self-update to the exact release SHA;
- release CI was 5/5 green;
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

Draft PR #135 fixes only that coupling and adds a delayed-composer regression test. Exact repair SHA:

`25e817c79086f3962a4cee1b23515a11ebedffd3`

The exact SHA has a complete 5/5 green CI run, including `bridge-browser` and `macos-smoke`.

## Next acceptance sequence

Do not broaden scope before this sequence is complete:

1. finish documentation/branch housekeeping without Local Agent execution;
2. review PR #135 as the only code repair candidate;
3. make an explicit merge/deploy decision;
4. after deployment, verify exact installed revision from fresh status;
5. run one bounded child pilot;
6. if and only if that pilot succeeds, decide whether to configure Conversation Operator intake for real parent fan-out;
7. add normal diagnostics for Conversation Operator enabled/configured state before relying on it operationally.

Do not repeat the historical manual Chrome login / Cloudflare / DOM-proof loop. If the bounded pilot still fails, capture the exact new failure and continue from that evidence.

## Deferred maintenance

Keep these separate from the child repair:

- large Growclip/BloomML worktrees and storage hygiene;
- `hardware-lab` sparse/partial-clone policy drift;
- operator observability improvements;
- broad fleet scheduling, automatic rollover and large fan-out.
