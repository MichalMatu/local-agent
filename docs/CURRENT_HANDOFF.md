# Current handoff — post-self-diagnostic Superchat baseline

Date: 2026-10-04

Status: Local Agent 4.20.5 / Chat Bridge 0.8.1 is released and live. Parent-level Superchat coordination is healthy. The remaining functional blocker is optional child-browser delegation; the executor, scheduler, target-repository routing and process-lifecycle boundaries passed the 2026-10-04 self-diagnostic.

## Read this first

Repository state, durable docs and fresh runtime evidence outrank chat memory.

Read in this order:

1. `AGENTS.md`
2. this file
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/conversation_fabric/CURRENT_PLAN.md`
6. `docs/DEVELOPMENT_PLAN.md`
7. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`
8. `docs/conversation_fabric/SELF_DIAGNOSTIC_2026-10-04.md`

## Current release state

- released/tagged runtime commit: `v4.20.5` = `bd793d60c3bce4b247deb80a7e2bfc88e8bf4373`;
- Local Agent release/runtime version = 4.20.5;
- Chat Bridge release source = 0.8.1;
- exact release CI = 5/5 green;
- production completed the natural self-update to that exact release commit;
- no forced restart was used to obtain that state;
- `main` may advance beyond the release tag for verified documentation-only maintenance; do not infer the installed runtime revision from current `main`.

The previous parent conversation control `chat-7781d9b9` was disabled during the self-diagnostic so it cannot continue periodic wakes in parallel with later Superchat work.

## Accepted architecture

```text
Parent Superchat
  -> reasoning / decomposition / coordination
  -> GitHub durable control/evidence
  -> optional bounded child reasoning chats
  -> direct GitHub edits or exact target .agent/tasks
  -> verified results
  -> parent synthesis / next decision
```

Chat identity is transport/scheduling identity only. Repository names and `repository_id(s)` in reasoning are context, not machine authority. Donor and target repositories may differ without `LAB:REBIND`.

The only executable repository-work boundary remains:

```text
registry binding == target .agent/binding.json binding == task.agent_binding
```

`.agent/tasks` is the only executable repository-work contract. `local-agent` remains `execution_enabled: false` and must not receive Local Agent tasks.

## 2026-10-04 self-diagnostic result

No P0/P1 regression was found in:

- scheduler/control and bounded parallel admission;
- exact target-repository routing/binding;
- process registration, process groups, termination and resource leases;
- parent Superchat transport-only architecture.

Maintenance findings remain for storage/worktree size and operator observability, but they are not release blockers.

The detailed checkpoint is `docs/conversation_fabric/SELF_DIAGNOSTIC_2026-10-04.md`.

## Child reasoning path

Child delegation is not yet production-trustworthy.

Current facts:

- Conversation Operator intake remains default-disabled unless explicitly configured;
- current production LaunchAgent configuration does not enable that intake;
- the implemented MVP child-spawn backend still uses the isolated browser actuator;
- the earlier live pilot stopped at `chatgpt_login_timeout` before child registration.

The self-diagnostic isolated a concrete defect: login/session probing was gated on composer DOM visibility. Draft PR #135 (`work/selfdiag-child-auth-decouple-20261004`) decouples session authentication from composer readiness and adds a delayed-composer regression test. It is now one clean commit directly on the post-cleanup `main`: `ba884c206925e6e25041657a0250a9459e3aa8f2`. Fresh CI on that exact head is 5/5 green, including `bridge-browser` and `macos-smoke`.

Do not return to long manual Chrome login / Cloudflare / DOM debugging. The next child-path action, after an explicit merge/deploy decision for PR #135, is one bounded pilot.

## Branch policy

Permanent operational branches are:

- `main`
- `chat-bridge-state`
- `operator-control`

Temporary branches are retained only while they back an active PR or contain unique unmerged evidence.

Current disposition:

- keep `work/selfdiag-child-auth-decouple-20261004` for draft PR #135;
- `work/selfdiag-report-20261004` is only the temporary carrier for this final documentation reconciliation and is safe to delete after merge;
- `work/superchat-final-cleanup-v4.20.5-20261003` is merged/released history and is safe to delete;
- `work/conversation-fabric-simplify-binding-v4.20.4-20261003` is an obsolete pre-4.20.5 work line and is safe to retire after the final compare already performed;
- `develop/conversation-fabric` and `archive/conversation-fabric-pre-rebase` are historical pre-consolidation lines, no longer canonical, and are safe to retire after durable documentation captured their relevant state.

## Next step

The next code step is deliberately narrow:

1. review PR #135 only against the child-auth failure mechanism;
2. merge only after an explicit decision;
3. allow normal deployment/self-update behavior rather than forcing an active task to drain;
4. confirm the exact deployed revision;
5. run one bounded child pilot;
6. only after that pilot passes consider enabling Conversation Operator intake for real parent fan-out.

Do not start a new release or broad architectural expansion before that evidence chain is complete.

## Non-negotiable invariants

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic/model-free.
- Chat Bridge remains browser transport/scheduling, not repository authorization.
- Child chats never receive independent machine execution authority.
- `.agent/tasks` remains the exact target execution boundary.
- No second Conversation Fabric scheduler/control plane.
- No local Codex/other coding-agent CLI through Local Agent.
- No production/daily Chrome profile mutation.
- `chat-bridge-state` and `operator-control` are operational state branches, not development branches.
