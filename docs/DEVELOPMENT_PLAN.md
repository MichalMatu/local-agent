# Local Agent development plan

Status: the parent Superchat transport/routing model is accepted. The next product milestone is a clean Local Agent self-diagnostic run coordinated by the parent Superchat, with bounded child reasoning where the child browser path is healthy.

## Current release line

- released baseline before this cleanup: Local Agent v4.20.4 / Chat Bridge 0.8.0;
- prepared cleanup release: Local Agent v4.20.5 / Chat Bridge 0.8.1;
- `main` remains the production source of truth after release;
- `chat-bridge-state` is operational schedule/runtime desired state, not a development branch;
- `operator-control` is global safety/control state, not a development branch.

Temporary release/development branches and worktrees must be removed after final production proof. The old long-lived `develop/conversation-fabric` line is no longer the canonical runtime development line once its durable documentation has been reconciled into `main`.

## Product direction

```text
User
  -> Parent Superchat (reasoning coordinator)
    -> GitHub durable control/evidence
    -> optional bounded child reasoning chats
    -> exact target-repository .agent/tasks for machine work
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

- GitHub-managed parent Superchat wake was delivered and answered in the intended conversation.
- Parent chat `chat-7781d9b9` operated without repository binding fields in its GitHub `conversation_controls` record.
- A read-only MatrixHub task proved transport-only multirepo reasoning still routes execution through MatrixHub's exact canonical binding and repository checkout, with no edits.
- Conversation Fabric request schema v3 supports ordered `repository_ids` as reasoning context rather than execution identity.
- The browser child-spawn pilot currently has one known concrete blocker: `chatgpt_login_timeout` from the isolated-profile login detector. Parent operation does not depend on this path.

## Current milestone: Superchat self-diagnostic

The first clean product test should use Local Agent as its own audit subject. The parent Superchat should establish exact runtime state, divide the audit into at most four bounded tracks, delegate reasoning where practical, coordinate findings and approve any fixes.

Suggested tracks:

1. daemon/supervisor/executor/task contract, bindings, leases/resources and recovery;
2. Git control/publication/self-update/emergency controls and stale-state handling;
3. Chat Bridge transport, GitHub scheduling, popup/onboarding and retry/error ownership;
4. Conversation Fabric parent/child lifecycle and the known child login-detector failure.

Children audit/debug/verify and propose fixes. They never queue machine work independently. The parent is responsible for deduplication, target selection, exact-bound task creation, verification and synthesis.

If child spawn is still blocked, fix that boundary only from bounded evidence; do not repeat the historical Chrome login/Cloudflare/DOM-proof loop. The parent should continue the rest of the audit while that subsystem is repaired.

## Verification discipline

For every concrete repair:

1. prove the failure mechanism from code/runtime evidence;
2. make the smallest scoped change;
3. run focused positive/negative checks;
4. preserve exact target `.agent/tasks` binding and executor admission;
5. avoid duplicate tasks/branches;
6. run one final broad repository gate;
7. leave a durable checkpoint with exact commit/result evidence.

Broad fleet scheduling, automatic conversation rollover and large fan-out remain later milestones and must not be introduced during the self-diagnostic pilot.
