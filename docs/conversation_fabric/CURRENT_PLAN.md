# Conversation Fabric — current execution plan

Status: parent Superchat transport is working end-to-end. The next milestone is a clean self-diagnostic pilot of Local Agent using the parent Superchat as coordinator.

## Baseline

- released production before this candidate: Local Agent v4.20.4 / Chat Bridge 0.8.0 on `main@cfa0a2380784d6cb2e5ae79cb8d92a3b52158fe5`;
- prepared cleanup candidate: Local Agent v4.20.5 / Chat Bridge 0.8.1 on `work/superchat-final-cleanup-v4.20.5-20261003`;
- parent Superchat proof conversation: `chat-7781d9b9` (`https://chatgpt.com/c/6ac07e18-0398-83ed-9aaa-609e731f2f9e`);
- GitHub-managed wake delivery to that parent was proven live;
- read-only MatrixHub routing proof passed with the exact MatrixHub task binding and repository checkout;
- Conversation Fabric supervisor operator intake remains default-disabled unless explicitly configured.

## Permanent architecture

```text
Parent Superchat
  -> decomposes/coordinates reasoning work
  -> GitHub durable control/evidence
  -> optional bounded child reasoning chats
  -> exact target .agent/tasks for machine execution
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

## Known child-browser issue

A post-4.20.4 child pilot reached the existing browser spawn path but stopped at `chatgpt_login_timeout` even though the isolated profile had previously been authenticated. Do not repeat login/Cloudflare/DOM loops as a parent-Superchat acceptance gate.

Treat that path as a separately repairable subsystem. In the self-diagnostic pilot the parent should first audit the child transport/login detector from durable code/evidence and decide the smallest repair. Until it is reliable, the parent can continue coordinating GitHub work and exact-bound Local Agent tasks without child browser delegation.

## Next acceptance scenario: Local Agent self-diagnostic

Start a fresh Superchat and ask it to diagnose Local Agent itself. The parent should:

1. establish exact release/daemon/registry/Bridge/control-plane state from fresh evidence;
2. divide the audit into a small number of bounded tracks (for example runtime/executor, Git/control/recovery, Bridge transport, Conversation Fabric child path);
3. delegate reasoning tracks to child chats when the child path is healthy; otherwise record the exact blocker and continue parent-led auditing without inventing a second execution path;
4. let children audit/debug/propose fixes only; machine effects remain parent-approved exact-bound `.agent/tasks` or direct GitHub edits;
5. prioritize concrete defects and regressions over architectural expansion;
6. run focused verification for each repair and one final broad gate;
7. produce a durable result/checkpoint describing findings, fixes, remaining risks and whether child delegation is trustworthy.

This scenario is the first real product acceptance test. Broad fleet scheduling, automatic rollover and large fan-out remain out of scope.
