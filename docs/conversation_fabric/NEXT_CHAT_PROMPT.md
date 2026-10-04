# Next chat prompt — bounded primary-Chrome live acceptance

Use this for a fresh bounded acceptance when Chat Bridge `0.8.3` is loaded in the operator's normal Chrome session.

---

Continue `MichalMatu/local-agent`, but do not use prior-chat memory as source of truth.

Read fresh:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/conversation_fabric/README.md`
6. `docs/conversation_fabric/CURRENT_PLAN.md`

Goal: run one bounded real Conversation Fabric acceptance in the already authenticated primary Chrome session. Do not repair or use an isolated profile, `chat-bridge-cft`, CDP, another production browser process, cookie migration or manual Cloudflare/login flow.

Before delegating, verify fresh `main`, exact installed Local Agent `self_revision`, Chat Bridge `0.8.3`, the exact managed parent conversation/tab and its GitHub `conversation_controls` record.

Delegate 3–4 narrow non-overlapping reasoning-only children using one exact trailing `LOCAL_AGENT_CF` delegate block. Include all source context each child needs. Children may inspect/reason from bounded repository evidence but may not create `.agent/tasks`, run machine commands, mutate repositories or make the final parent decision.

Require at least one child to complete quickly and another to remain active longer. Verify that the children open as ordinary tabs in the same existing Chrome session. Keep the managed parent and Master enabled while the existing minute GitHub-control alarm collects results automatically. Do not use LAB scheduling markers. Modify the exact GitHub `conversation_controls` record only when changing remotely managed parent pacing.

During the active campaign exercise a real service-worker/extension lifecycle interruption when the harness/operator can do so safely. Confirm that already captured stable results remain durable, exact child ownership is recovered only from transaction/request/bootstrap/current-URL evidence, and no submitted child bootstrap is replayed. Exercise at least one transient observation failure and confirm later recovery.

An explicit `LOCAL_AGENT_CF` collect block may inspect/recover already-submitted children after an observation failure without replaying their prompts. It is not the normal polling mechanism.

Require stable result capture, final collection, exact owned child-tab cleanup and one terminal parent feedback delivery. Then reload/restart the Bridge worker again, poll/reconcile again, and verify the completed campaign is not replayed.

If real machine execution is justified, resolve the actual target repository through the canonical runtime catalog, require `execution_enabled=true`, and queue at most one bounded `.agent/tasks` item with that target's exact canonical `agent_binding` and a stable branch-scoped `dedupe_key`. The current canonical catalog enables `local-agent`; self-execution is permitted only through the same catalog, binding, lease, resource and emergency-control gates as every other enabled target. If machine execution is not needed, create no task.

Also cover runtime admission with production-shaped cases: valid task, wrong binding, execution-disabled target, stale/unknown registry identity, dedupe collision, malformed dedupe metadata, and intended serial/parallel semantics.

Verify no equivalent duplicate work ran. End the managed parent in its intended paused state unless continued automation is explicitly required. Record PASS / PARTIAL / FAIL with exact evidence, relevant commit/run ids and one next blocker if any.

---
