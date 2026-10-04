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

Goal: run one bounded real Conversation Fabric acceptance in the already authenticated primary Chrome session. Do not repair or use an isolated profile, `chat-bridge-cft`, CDP, another browser process, cookie migration or manual Cloudflare/login flow.

Before delegating, verify fresh `main`, exact installed Local Agent `self_revision`, Chat Bridge `0.8.3`, the exact managed parent conversation/tab and its GitHub `conversation_controls` record.

Delegate at least two narrow non-overlapping reasoning-only children using one exact trailing `LOCAL_AGENT_CF` delegate block. Children may inspect/reason from bounded repository evidence but may not create `.agent/tasks`, run machine commands, mutate repositories or make the final parent decision.

Verify that the children open as ordinary tabs in the same existing Chrome session. Keep the managed parent and Master enabled while the existing minute control poll collects results automatically. Do not use LAB scheduling markers. Modify the exact GitHub `conversation_controls` record only when changing remotely managed parent pacing.

Wait for actual result feedback. An explicit `LOCAL_AGENT_CF` collect block may inspect already-submitted children after an observation failure without replaying their prompts. Require stable child results, verify the owned child tabs are retired/closed, then synthesize the final parent decision.

If real execution is justified, resolve the actual target repository from the runtime catalog and queue at most one bounded `.agent/tasks` item with that repository's exact canonical `agent_binding` and a stable branch-scoped `dedupe_key`. `local-agent` itself remains execution-disabled. If execution is not needed, create no task.

Verify no equivalent duplicate work ran. End the managed parent in its intended paused state unless continued automation is explicitly required. Record PASS / PARTIAL / FAIL with exact evidence and one next blocker if any.

---
