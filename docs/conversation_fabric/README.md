# Conversation Fabric

**Current operator handoff (2026-10-10):**
[GitHub-first current handoff](GITHUB_FIRST_CURRENT_HANDOFF.md) and
[manual next-chat prompt](GITHUB_FIRST_NEXT_SUPERCHAT_PROMPT.md).

**Verified in the operator's existing authenticated Chrome:** Bridge
**0.8.18**, one private GitHub-first reasoning child, with independently
confirmed private `claim → ACK → result`. This is not multi-child or
cross-device acceptance; PR #274 is still draft and `main` is untouched.
See the [single-child live runbook](GITHUB_FIRST_MVP_TRIAL.md).

**Separate, earlier working path:** the **legacy DOM** Conversation Fabric
accepted one and three reasoning children on Bridge 0.8.13 (2026-10-08).
See [legacy current plan](CURRENT_PLAN.md) and
[historical 0.8.13 acceptance](CHECKPOINT_2026-10-08_BRIDGE_0813_LIVE_ACCEPTANCE.md).
Legacy DOM parallel acceptance does **not** prove GitHub-first private
multi-child support.

The [2026-10-10 E2E readiness runbook](E2E_READINESS_2026-10-10.md)
records the earlier **pre-live** gate and is historical for the private path.
[TARGET_PRODUCT_ARCHITECTURE.md](TARGET_PRODUCT_ARCHITECTURE.md) is the
future target, not an implementation-status report.

## Responsibility boundaries

| Component | Authority |
| --- | --- |
| ChatGPT parent | Decides whether to delegate/synthesize; no repository execution grant |
| Chat Bridge extension | Exact `LOCAL_AGENT_CF` admission, child-tab lifecycle, bounded result/vault capture, at-most-once terminal feedback |
| GitHub `chat-bridge-state` | Remote conversation pacing and managed desired state; **not** child-tab executor |
| Local Agent | Canonical catalog/binding admission and deterministic repository/machine execution |

Children are reasoning-only. Do not delegate machine actions or automatically replay child bootstrap prompts. Production uses no secondary Chrome profile, CDP attachment or Native Messaging.

## Legacy DOM implementation map

- `chat_bridge/conversation_fabric_protocol.js` — control schema and bounds.
- `chat_bridge/conversation_fabric_content.js` — read final parent control; append plain ASCII child completion proof.
- `chat_bridge/worker_conversation_fabric*.js` — admission, recovery, stable result collection, vault and terminal delivery.
- `chat_bridge/worker_spawn*.js`, `chat_bridge/spawn_result_content.js` — exact owned Chrome tabs, bootstrap and result proof.
- `scripts/conversation_fabric_dom_smoke.cjs`, `scripts/conversation_fabric_browser_smoke.cjs` — Chromium regressions; real Chrome acceptance remains separate.

## Branch and documentation hygiene

`main` holds source. `agent-control`, `chat-bridge-state` and `operator-control` are control/evidence branches and **must not** be treated as disposable feature branches. `work/*` is temporary; PR merge does not automatically delete a work branch.

Historical dated proof, isolated-profile DEV-lab and Stage 8 handoff files remain read-only audit evidence. They are not current runbooks. Use `CURRENT_PLAN.md` for current behavior, not old prompts.
