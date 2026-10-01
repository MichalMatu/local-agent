# Local Agent development plan

Status: current post-checkpoint development direction, prepared for the v4.19.11 release checkpoint.

## Production checkpoint

The current candidate is Local Agent 4.19.11 / Chat Bridge 0.6.2. Runtime schema 3, content protocol v13 and assistant guard v8 are unchanged.

The candidate has completed the terminal-safety repair, historical BUG-001 closure revalidation, release-engineering hardening, full CI/macOS/browser verification and the bounded live GitHub-control browser proof. The live control was returned to PAUSED after the successful short-interval wake test.

Remaining release actions are administrative: final documentation CI, explicit merge of PR #122, tag v4.19.11, clean installed-checkout verification and deletion of the obsolete checkpoint branch after production proof.

## Product direction

The canonical target is one user-visible Local Agent product with one long-lived Operator Chat / Superchat.

```text
User
  -> Operator Chat / Superchat
    -> GitHub control + evidence plane
      -> Local Agent deterministic orchestration/execution
        -> host-ops deterministic capabilities
        -> narrow ChatGPT Browser Driver for child-chat UI lifecycle
      -> GitHub result/evidence
    -> Operator Chat synthesis
```

Permanent architecture rules:

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- Ordinary ChatGPT conversations remain the reasoning layer.
- Chat Bridge is reduced to a narrow browser lifecycle/transport role.
- Browser DOM is transport evidence, never workflow/task authority.
- Child chats never gain independent machine authority.
- MCP and direct OpenAI API model loops are excluded from the current target architecture, fallback path and future roadmap unless the architecture is explicitly changed.

## Development lane

| Lane | Branch | Role |
| --- | --- | --- |
| Production | main | released runtime and installed source of truth |
| Development | develop/conversation-fabric | canonical Conversation Fabric / Superchat development line |
| Operational state | chat-bridge-state | GitHub-backed Chat Bridge desired state |
| Operational control | operator-control | global operator safety/control state |
| Release candidate | work/checkpoint-v4.19.11 | disposable validation branch; delete after production proof |

No other long-lived work branch should be created without an explicit reason.

## Next development milestone

The next implementation line is Conversation Fabric Stage 8 — bounded live child-chat slice on develop/conversation-fabric.

The first live gate is intentionally small:

1. use the isolated DEV checkout/profile, never production;
2. seed exactly one non-executing reasoning request for MichalMatu/local-agent;
3. prepare one exact durable attempt;
4. prove login/composer readiness;
5. arm the exact plan digest;
6. create exactly one ChatGPT child;
7. discover its canonical /c/<id> URL;
8. persist the exact ChildRegistration and SpawnTransaction=done;
9. inspect the bootstrap and durable evidence;
10. only then extend the live slice to adoption/terminal/retirement.

Current Stage 8 safety limits:

- maximum active children: 1;
- maximum browser spawn attempts: 1;
- local-agent remains execution_enabled=false;
- no production Chrome profile;
- no production Native Messaging registration;
- no automatic production Superchat scheduler;
- no second Local Agent executor;
- ambiguous create/submit state fails closed and never blindly replays.

Do not start the 44-node acceptance campaign from this gate.

## After Stage 8

1. Stage 8 live proof — one real child create/register.
2. Stage 8 lifecycle extension — adoption, terminal recording and retirement.
3. Recovery proof — restart/reconcile every external-effect boundary without duplicates.
4. Manual lifecycle parity — keep prepare/open/paste/attach as a first-class fallback.
5. Narrow Browser Driver promotion — automate only physical ChatGPT child lifecycle effects.
6. Superchat control/fleet layer — only after the single-child lifecycle is proven.
7. Automatic scheduling — only if required after the complete lifecycle is stable.

The conceptual Superchat lifecycle roadmap remains in docs/superchat/ROADMAP.md. The canonical execution-stage ledger remains on develop/conversation-fabric in docs/conversation_fabric/CURRENT_PLAN.md.

## Verification discipline

Every non-trivial change must start from the correct canonical branch, preserve hard repository binding and GitHub authority, use focused tests first, use real lifecycle evidence for browser/process/resource boundaries, run exact-SHA CI before release, keep production and DEV state separate, update the current handoff when a milestone changes and remove obsolete candidate branches after production proof.

Exact GitHub task/run/result/control evidence outranks chat prose or browser appearance.
