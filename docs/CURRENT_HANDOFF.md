# Current handoff — transport-only Superchat baseline

Date: 2026-10-03

Status: parent Superchat transport and exact target-repository execution routing are proven. Local Agent 4.20.5 / Chat Bridge 0.8.1 is the final cleanup candidate before starting a fresh self-diagnostic Superchat.

## Read this first

Repository state, durable docs and fresh host evidence outrank chat memory.

Read in this order:

1. `AGENTS.md`
2. this file
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/conversation_fabric/CURRENT_PLAN.md`
6. `docs/DEVELOPMENT_PLAN.md`
7. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

## Current release state

Released baseline before this cleanup candidate:

- `main@cfa0a2380784d6cb2e5ae79cb8d92a3b52158fe5`
- tag `v4.20.4` at the same commit
- Local Agent 4.20.4
- Chat Bridge 0.8.0

Prepared final cleanup:

- branch `work/superchat-final-cleanup-v4.20.5-20261003`
- Local Agent 4.20.5
- Chat Bridge 0.8.1
- contains the five post-4.20.4 Bridge fixes that were proven live but had remained only on the old work branch: popup Add-current-chat fix, minimal chat envelope, assistant-error ownership update and matching tests
- active documentation is being reconciled to the transport-only model before merge

After release, verify exact `main`, matching `v4.20.5` tag and installed daemon `self_revision`; do not infer deployment from this handoff.

## Accepted Superchat model

```text
Parent Superchat
  -> reasoning / decomposition / coordination
  -> GitHub durable control/evidence
  -> optional bounded child reasoning chats
  -> direct GitHub edits or exact target .agent/tasks
  -> verified results
  -> parent synthesis / next decision
```

The parent chat is **not** hard-bound to one repository for reasoning. The active goal or durable Conversation Fabric request may name donor and target repositories without Rebind.

Bridge conversation identity is transport/scheduling identity only. Legacy `planner_scope`, repository/binding metadata and ADD/REBIND commands may remain for compatibility or migration, but they are not repository authorization evidence.

The real execution boundary is unchanged:

```text
registry binding == target .agent/binding.json binding == task.agent_binding
```

`.agent/tasks` is the only executable repository-work contract. Execution-enabled admission, repository identity, leases/resources, watchdogs, cancellation and emergency disable remain fail-closed.

The `local-agent` catalog entry remains `execution_enabled: false` and must not receive an executable Local Agent task.

## Live proof

Parent Superchat:

- conversation URL: `https://chatgpt.com/c/6ac07e18-0398-83ed-9aaa-609e731f2f9e`
- Bridge id: `chat-7781d9b9`
- GitHub-managed wake was delivered to the intended conversation and received a normal ChatGPT response
- its `conversation_controls` record was reduced to chat-scoped schedule state without repository/binding authority

Execution routing:

- MatrixHub read-only routing task: `superchat-multirepo-routing-proof-matrixhub-20261003-v1`
- exact target binding: `033327ab-700d-43b4-9b3b-caff1acaa2c7`
- observed origin: `https://github.com/MichalMatu/MatrixHub.git`
- output: `ROUTING_PROOF=PASS`
- no repository edits

This proves loosening the parent chat binding did not loosen executable target binding.

## Child reasoning path

Conversation Fabric child lifecycle and GitHub request/result boundary remain implemented. Operator intake remains default-disabled unless explicitly configured.

A post-4.20.4 child-browser pilot used a v3 request with `local-agent + matrixhub` reasoning context. It failed before child registration with `chatgpt_login_timeout` from the isolated-profile login detector, despite the profile having previously been authenticated.

Do **not** return to the historical DEV Chrome login / Cloudflare / DOM-proof loop. Parent Superchat operation is already proven independently. Treat child-browser spawn/login detection as a bounded subsystem to diagnose and repair during the next self-diagnostic phase.

## Branch/worktree cleanup policy

Permanent operational branches after cleanup should be only what remains necessary:

- `main`
- `chat-bridge-state`
- `operator-control`

Temporary release/work branches and stale local branches whose remotes are gone should be removed after 4.20.5 merge/tag/live proof. The old `develop/conversation-fabric` and `archive/conversation-fabric-pre-rebase` branches should be retained only if a final compare against released `main` proves unique required content; otherwise retire them as part of this cleanup.

Candidate/development worktrees should likewise be removed after proof. Keep the production checkout `/Users/michal/local-agent` clean on released `main`.

## Next phase

Open a fresh Superchat and run Local Agent self-diagnostics. The parent should establish fresh exact state, split the audit into bounded tracks, delegate reasoning to child chats when healthy, coordinate findings, approve exact-bound machine work and synthesize results.

The known child login detector should be one bounded audit/repair track, not a prerequisite for the other parent-led diagnostics.

Use `docs/conversation_fabric/NEXT_CHAT_PROMPT.md` as the ready-to-paste start prompt.

## Non-negotiable invariants

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic/model-free.
- Chat Bridge remains browser transport/scheduling, not repository authorization.
- Child chats never receive independent machine execution authority.
- `.agent/tasks` remains the exact target execution boundary.
- No second Conversation Fabric scheduler/control plane.
- No local Codex/other coding-agent CLI through Local Agent.
- No production/daily Chrome profile mutation.
- Do not use `chat-bridge-state` or `operator-control` as development branches.
