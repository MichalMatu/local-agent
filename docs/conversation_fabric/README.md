# Conversation Fabric

Browser-native reasoning-child delegation for one managed ChatGPT parent in the operator's authenticated Chrome profile. **Chat Bridge 0.8.13 / content protocol v26** is the current source contract.

## Start here — choose one track

- **GitHub-first Milestone 8 / private cross-device project continuity:** [**current, source-verified handoff (2026-10-09)**](GITHUB_FIRST_CURRENT_HANDOFF.md). This is the only active Milestone 8 continuation entrypoint. GitHub-first browser execution remains disabled; PR #209 is a synthetic-only parent-mode preview.
- **Existing production Chrome/DOM child delegation:** [current DOM behavior and restart gate](CURRENT_PLAN.md), [live Chrome acceptance checkpoint](CHECKPOINT_2026-10-08_BRIDGE_0813_LIVE_ACCEPTANCE.md), [diagnostics](DELEGATION_DIAGNOSTICS.md).
- **Target product ownership:** [GitHub-first target architecture](TARGET_PRODUCT_ARCHITECTURE.md).

Older handoff prompts and pre-publisher plans are historical evidence; follow the current handoff above, not stale SHA references or prior suggested work.

## Legacy DOM live status (2026-10-08)

- **PASS:** one verification child in campaign `cf-a9f08cda8905ab33`.
- **PASS:** three parallel research/verification/integration children in campaign `cf-df084c77d84a5929`.
- Both campaigns reported stable capture and automatic owned-tab cleanup in the operator's normal Chrome.
- **NOT YET LIVE-VERIFIED:** reload/restart of the extension while children are running, with claim-safe recovery and no replay.
- An earlier child attempt failed when its tab was manually closed before Bridge collected a valid legacy completion footer. It is historical failure evidence, not an active campaign.

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
