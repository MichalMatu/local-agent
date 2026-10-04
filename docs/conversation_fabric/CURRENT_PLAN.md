# Conversation Fabric current plan

## Goal

Run one bounded live Superchat acceptance on real code and prove the intended product behavior: one parent delegates reasoning, observes children, synthesizes the result and retains sole authority to request deterministic execution.

## Preconditions

Before starting the proof, verify fresh evidence rather than assuming:

- current `main` and installed Local Agent `self_revision`;
- Local Agent release line `4.20.6` and Chat Bridge `0.8.1`;
- no open code-repair PR blocking child lifecycle;
- exact Bridge control state for the new parent conversation;
- Conversation Operator/browser configuration and whether intake is enabled;
- chosen target repository is execution-enabled and has a canonical binding.

Operator intake may be enabled explicitly for the bounded proof if the supported runtime configuration requires it. Do not leave it enabled accidentally after the proof.

## Acceptance sequence

1. Start one fresh parent Superchat from `NEXT_CHAT_PROMPT.md`.
2. Choose one small real-code goal in an execution-enabled repository. Prefer a task with clear evidence and bounded verification; avoid broad refactors.
3. Parent creates at least two reasoning-only children with non-overlapping assignments, for example:
   - child A: narrow code/architecture audit;
   - child B: independent tests/failure-mode/review analysis.
4. Give children pinned repository/commit context and a bounded output contract. No child may create `.agent/tasks` or run machine commands.
5. Parent waits for/reads both child results and records exact child lifecycle evidence.
6. Parent reconciles disagreements and decides whether a code change is justified.
7. If execution is justified, parent creates exactly one bounded target-repository task with the exact canonical binding and a stable branch-scoped `dedupe_key` for that logical intent.
8. Observe one Local Agent execution/result. Confirm no equivalent duplicate task/build/test runs.
9. Verify resulting repository/CI evidence only as needed for the goal.
10. Retire/close owned child lifecycle state and return operator/Bridge scheduling to the intended paused state when the bounded proof ends.
11. Record PASS / PARTIAL / FAIL with exact evidence and any single next blocker.

## Stop conditions

Stop rather than weakening safety if any of these occurs:

- child authentication/ownership is ambiguous;
- two authoritative child generations appear for one child slot;
- a child obtains machine execution authority;
- target binding/repository identity is uncertain;
- equivalent expensive tasks execute twice;
- the parent cannot observe durable child result evidence.

Do not return to repeated manual login/Cloudflare/DOM experimentation as an acceptance strategy.

## Success criteria

The milestone passes only when the user can visibly see one Superchat parent orchestrating real child work and, when needed, exactly one deterministic Local Agent execution on real code.
