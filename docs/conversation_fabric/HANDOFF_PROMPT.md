# Conversation Fabric Stage 8 — continuation prompt

Use this prompt to start a fresh implementation conversation. `docs/CURRENT_HANDOFF.md` remains the authoritative state checkpoint.

```text
Continue Conversation Fabric Stage 8 in MichalMatu/local-agent.

Work in Local Agent mode and use the repository as authority, not remembered chat context.

Read, in order:
1. AGENTS.md
2. docs/CURRENT_HANDOFF.md
3. docs/conversation_fabric/CURRENT_PLAN.md
4. docs/DEVELOPMENT_PLAN.md

Before changing anything, verify the actual GitHub head of develop/conversation-fabric and compare it with the handoff. Production main must remain untouched.

Mac rule: use host-ops for every Mac-local operation: checkout/worktree changes, local tests, browser/profile inspection and live proof execution. Use direct GitHub operations for repository inspection and repository-side changes.

The last accepted runtime/code baseline is b6f9ce3bb47309474dba7c430df3880912aaa4ef. The actual develop/conversation-fabric head may be later because handoff documentation can advance independently; verify GitHub rather than assuming the code-baseline SHA is the branch head.

The preserved Stage 8 attempt stage8-live-child-001 / spawn-3c78a92eb001f46790989f4da8fea0bcca6b1d55035770b7dc48ef40bd72a032 is terminal ambiguous evidence. Do not retry, reset, rewrite or delete it.

The active task is the composer DOM replacement blocker. Continue on work/conversation-composer-replacement. Implement the smallest safe fix so a replaced active composer may continue only when its text still exactly equals the inserted bootstrap; different/operator-edited text must remain untouched and unsent. Preserve all existing route, transaction, digest, claim, send-button and post-submit ambiguity safeguards.

Add/repair a real browser regression test that replaces the composer DOM node between insertion and the final pre-submit check. Keep the existing operator-edit negative proof. Run focused tests plus both Conversation Fabric browser smokes through host-ops. Require full exact-SHA CI before fast-forwarding develop/conversation-fabric.

After promotion, create a fresh isolated DEV live state namespace. Do not reuse the ambiguous attempt. Execute exactly one step per invocation: seed -> prepare -> login -> arm -> run. Never auto-retry run.

Stage 8 is complete only after one fresh proof produces exactly one real https://chatgpt.com/c/<id>, matching ChildRegistration, SpawnTransaction=done and bounded completion evidence, with no child execution authority and no production Chrome/profile mutation.

Stop after that proof and review the evidence before starting later lifecycle work.
```
