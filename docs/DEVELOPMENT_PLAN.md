# Local Agent development plan

Status: Local Agent 4.20.5 / Chat Bridge 0.8.1 is released and live. Parent Superchat coordination is accepted. The next product milestone is to make the optional child reasoning path trustworthy with one narrowly scoped repair and one bounded live pilot.

## Current release line

- released/tagged runtime commit: `v4.20.5` = `bd793d60c3bce4b247deb80a7e2bfc88e8bf4373`;
- production runtime naturally advanced to Local Agent 4.20.5 at that exact release commit;
- current `main` may advance beyond the release tag for verified documentation-only maintenance and is not itself proof of the installed runtime revision;
- Chat Bridge release source = 0.8.1;
- `chat-bridge-state` is operational schedule/runtime desired state, not a development branch;
- `operator-control` is global safety/control state, not a development branch;
- `local-agent` remains execution-disabled as a Local Agent task target.

Temporary development/release branches should exist only while backing an active PR or unique unmerged evidence. Long-lived pre-consolidation Conversation Fabric branches are historical, not canonical development lines.

## Product direction

```text
User
  -> Parent Superchat (reasoning coordinator)
    -> GitHub durable control/evidence
    -> optional bounded child reasoning chats
    -> direct GitHub work or exact target-repository .agent/tasks
    -> verified results
  -> Parent synthesis / next decision
```

Permanent boundaries:

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- ChatGPT conversations remain the reasoning layer.
- Chat Bridge is browser transport/scheduling, not repository authorization.
- Repository ids in prompts/Conversation Fabric requests are reasoning context only.
- Child chats have no independent machine execution authority.
- `.agent/tasks` is the only executable repository-work contract and always uses the exact target repository binding.
- No direct OpenAI API model loop and no second Conversation Fabric scheduler/control plane.
- No local Codex/other coding-agent CLI launched through Local Agent.

## Accepted evidence

The 2026-10-04 parent-led self-diagnostic established:

- Local Agent 4.20.5 is live on the exact release commit;
- scheduler/control, exact target binding/routing and process lifecycle/resource boundaries have no identified P0/P1 regression;
- the previous parent schedule was disabled to prevent duplicate periodic wakes;
- child delegation remains the one functional blocker;
- current production Conversation Operator intake is not enabled/configured.

The child-browser failure mechanism was narrowed to authentication probing being gated by composer DOM visibility. Draft PR #135 fixes that coupling only. It is now one clean commit on the post-cleanup `main`, `ba884c206925e6e25041657a0250a9459e3aa8f2`, with fresh exact-head CI 5/5 green.

## Current milestone: child delegation acceptance

Sequence:

1. keep PR #135 isolated from unrelated cleanup;
2. review the two-file repair and regression test;
3. merge only after an explicit decision;
4. let deployment/self-update follow normal safety rules;
5. verify exact deployed revision;
6. run one bounded child reasoning pilot;
7. only after the pilot passes decide whether to enable/configure Conversation Operator intake;
8. add operator configuration state to routine diagnostics before depending on fan-out operationally.

Do not repeat long manual Chrome login / Cloudflare / DOM experiments. Any remaining failure must be reduced from fresh bounded evidence.

## Deferred maintenance

Keep separate from the milestone above:

- workspace/storage optimization for large Growclip/BloomML worktrees;
- `hardware-lab` sparse/partial clone policy repair;
- broader operator observability;
- fleet-wide fan-out, automatic conversation rollover and broad autonomous scheduling.

## Verification discipline

For every concrete repair:

1. prove the failure mechanism from code/runtime evidence;
2. make the smallest scoped change;
3. run focused positive/negative checks;
4. preserve exact target `.agent/tasks` binding and executor admission;
5. avoid duplicate tasks/branches;
6. run one final broad repository gate;
7. leave a durable checkpoint with exact commit/result evidence.
