# Conversation Fabric continuation prompt

Use the text below for the next conversation after the 2026-10-04 self-diagnostic/documentation cleanup. Repository state, durable docs and fresh runtime evidence are authoritative; do not rely on previous chat memory.

---

Continue `MichalMatu/local-agent` from the post-self-diagnostic Superchat baseline.

Do not rely on memory from the previous chat. Read first:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/conversation_fabric/CURRENT_PLAN.md`
6. `docs/DEVELOPMENT_PLAN.md`
7. `docs/conversation_fabric/SELF_DIAGNOSTIC_2026-10-04.md`

Then establish exact current `main`, open PRs, installed daemon version/revision, `chat-bridge-state`, `operator-control` and active task state from fresh evidence.

Current expected baseline to verify, not assume:

- released source/tag: Local Agent 4.20.5 / Chat Bridge 0.8.1;
- release SHA: `bd793d60c3bce4b247deb80a7e2bfc88e8bf4373`;
- parent-level Superchat architecture is healthy;
- `local-agent` remains execution-disabled as a Local Agent task target;
- child delegation remains optional and not yet production-trustworthy;
- current production Conversation Operator intake is not enabled/configured;
- previous parent `chat-7781d9b9` should remain disabled.

Architecture is fixed:

- this parent chat is the reasoning/coordinating Superchat;
- Chat Bridge is transport/scheduling only, never repository authorization;
- repository names / `repository_id(s)` are reasoning context and donor/target repositories may differ without `LAB:REBIND`;
- child chats are bounded reasoning workers only;
- machine execution remains direct GitHub work when sufficient or exact target-repository `.agent/tasks` with the actual target's canonical `agent_binding`;
- `.agent/tasks` is the only executable repository-work contract;
- do not create a second scheduler/control plane and do not launch local Codex/another coding-agent CLI.

The immediate code candidate is draft PR #135, `Decouple child browser auth readiness from composer DOM`, exact head SHA `25e817c79086f3962a4cee1b23515a11ebedffd3`. The 2026-10-04 audit found that `waitForLoginReady()` gated authentication probing on composer DOM visibility. The PR decouples session authentication from composer readiness and adds a delayed-composer regression; an exact-SHA CI run completed 5/5 green.

First inspect PR #135 and current CI/diff. Do not mix unrelated cleanup into it. If it is still the correct minimal repair, make the explicit merge/deploy decision. After deployment, verify the exact installed revision and run **one bounded child pilot**. Do not return to the historical long Chrome login / Cloudflare / DOM debugging loop.

If the bounded pilot passes, then decide whether to configure Conversation Operator intake and add normal observability for its enabled/configured state. If it fails, capture the exact new failure and continue from that evidence instead of broadening architecture.

Keep storage/worktree optimization, `hardware-lab` clone-policy maintenance, broad fan-out and automatic rollover as separate later work.
