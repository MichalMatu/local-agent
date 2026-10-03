# Conversation Fabric continuation prompt

Use the text below to start the next ChatGPT conversation after the final cleanup release. Repository state, durable docs and fresh host evidence are authoritative; do not rely on previous chat memory.

---

Continue `MichalMatu/local-agent` in **Superchat self-diagnostic mode**.

Do not rely on memory from the previous chat. Repository state, durable documentation, GitHub control/evidence and fresh daemon state are the source of truth.

Read first:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/conversation_fabric/CURRENT_PLAN.md`
6. `docs/DEVELOPMENT_PLAN.md`
7. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

Then establish the exact current `main`, release tag, installed daemon revision/version, repository registry, `chat-bridge-state`, `operator-control`, Bridge version and active task state. Do not infer them from this prompt.

The architecture to test is already decided:

- this parent chat is the Superchat coordinator;
- Chat Bridge is transport/scheduling only and is **not** a repository authorization boundary;
- repository names in the active goal are reasoning context and may include donor + target repositories without `LAB:REBIND`;
- child chats, when used, are bounded reasoning workers only;
- the parent decomposes work, assigns audit/debug/verification scopes, reviews child conclusions and decides which fixes proceed;
- all machine execution remains through direct GitHub operations when sufficient or exact target-repository `.agent/tasks` with that repository's canonical `agent_binding`;
- `.agent/tasks` is the only executable repository-work contract;
- `local-agent` remains execution-disabled as a Local Agent task target;
- do not create a second scheduler/control plane and do not launch local Codex or another local coding-agent CLI.

Start with a **read-only self-audit of Local Agent**. Build a concise evidence-backed map of current health and divide it into at most four bounded workstreams, for example:

1. daemon/supervisor/executor/task-binding/resource/recovery correctness;
2. Git control, publication, self-update, emergency controls and stale-state cleanup;
3. Chat Bridge 0.8.x transport, GitHub-managed schedule, retry/error ownership and popup/onboarding;
4. Conversation Fabric parent/child lifecycle, with special attention to the known browser child-spawn login detector.

Delegate those workstreams to child chats if the child path is actually healthy. Children may audit, debug and propose patches, but they have no independent machine authority. The parent must coordinate, compare findings, avoid duplicate work and approve executable effects.

Known evidence from the previous stage: parent Superchat wake delivery worked; exact-bound MatrixHub routing passed; a later child-browser pilot stopped at `chatgpt_login_timeout` in the isolated profile. **Do not repeat the old Chrome login / Cloudflare / DOM-proof loop.** If that issue still exists, diagnose it from code and bounded fresh evidence, make it the first narrowly scoped repair, and continue the rest of the parent audit independently.

Prefer real defects over architectural expansion. For every fix: identify the failure mechanism, make the smallest change, run focused verification, and preserve executor safety boundaries. Finish with one broad gate and a durable checkpoint summarizing findings, fixes, unresolved risks and whether child delegation is now trustworthy enough for wider use.
