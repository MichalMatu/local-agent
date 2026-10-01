# Local Agent development plan

Status: current post-release development direction for Conversation Fabric Stage 8.

## Production checkpoint

Production is established as Local Agent v4.19.11 / Chat Bridge 0.6.2 on `main@0088f55ef37eecf26e0d4363f999797b9e340e96` with tag `v4.19.11` pointing to the same commit.

The release candidate work is complete. PR #122 is merged, the obsolete checkpoint branch has been removed and production `main` is the stable runtime/source-of-truth baseline.

The cleaned Conversation Fabric Stage 8 code baseline on `develop/conversation-fabric` was validated at `96c536a145904ae46add407004d9914d5088e215` with the complete canonical CI matrix green: test, coverage, Python 3.14, macOS smoke and Bridge browser smoke.

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
- Chat Bridge is a narrow browser lifecycle/transport role.
- Browser DOM is transport evidence, never workflow/task authority.
- Child chats never gain independent machine authority.
- `local-agent` remains `execution_enabled: false` for the Stage 8 reasoning-child slice.
- No second scheduler, executor or control plane.
- No direct OpenAI API model loop.
- No Native Messaging control plane or abandoned event-wake direction in the target architecture.

## Development lanes

| Lane | Branch | Role |
| --- | --- | --- |
| Production | `main` | released runtime and installed source of truth |
| Development | `develop/conversation-fabric` | canonical Conversation Fabric / Superchat development line |
| Operational state | `chat-bridge-state` | GitHub-backed Chat Bridge desired state |
| Operational control | `operator-control` | global operator safety/control state |
| Historical safety archive | `archive/conversation-fabric-pre-rebase` | preserved pre-cleanup development history; not an active development lane |

Temporary `work/conversation-*` branches may be used only for bounded validation candidates and must be removed after accepted state is promoted back to `develop/conversation-fabric`.

## Next development milestone

The next milestone is Conversation Fabric Stage 8 — the first bounded real child-chat proof on `develop/conversation-fabric`.

The first live gate is intentionally small:

1. perform exact-head preflight on `develop/conversation-fabric`;
2. use the isolated DEV checkout/profile, never production;
3. seed exactly one non-executing reasoning request for `MichalMatu/local-agent`;
4. prepare one exact durable attempt;
5. prove login/composer readiness;
6. arm the exact plan digest;
7. create exactly one ChatGPT child;
8. discover its canonical `/c/<id>` URL;
9. persist the exact `ChildRegistration` and `SpawnTransaction=done`;
10. inspect the bootstrap and durable completion evidence;
11. stop and review the proof before any lifecycle expansion.

Current Stage 8 safety limits:

- maximum active children: 1;
- maximum browser spawn attempts: 1;
- `local-agent` remains `execution_enabled=false`;
- no production Chrome profile;
- no production Native Messaging registration;
- no automatic production Superchat scheduler;
- no second Local Agent executor;
- ambiguous create/submit state fails closed and never blindly replays.

Do not start the larger acceptance campaign from this gate.

## After the one-child proof

Only after the bounded proof succeeds:

1. lifecycle extension — checkpoint/terminal recording, adoption and retirement;
2. restart/recovery proof across every external-effect boundary without duplicates;
3. manual lifecycle parity as a first-class fallback;
4. narrow Browser Driver promotion for physical ChatGPT child lifecycle effects only;
5. Superchat control/fleet layer after the single-child lifecycle is proven;
6. automatic scheduling only if required after the complete lifecycle is stable.

The conceptual Superchat lifecycle roadmap remains in `docs/superchat/ROADMAP.md`. The canonical Stage 8 execution ledger remains in `docs/conversation_fabric/CURRENT_PLAN.md`.

## Verification discipline

Every non-trivial change must start from the correct canonical branch, preserve hard repository binding and GitHub authority, use focused tests first, use real lifecycle evidence for browser/process/resource boundaries, run exact-SHA CI before promotion/release, keep production and DEV state separate, update the current handoff when a milestone changes and remove obsolete candidate branches after accepted promotion.

Before the Stage 8 live browser effect, re-check the exact development head and its validation evidence. Exact GitHub branch/commit/CI evidence outranks chat prose or browser appearance.
