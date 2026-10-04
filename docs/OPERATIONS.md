# Local Agent Operations

This is the canonical operational workflow for `MichalMatu/local-agent`.

## Production baseline

Release line:

```text
Local Agent 4.20.6
Chat Bridge 0.8.1
release tag v4.20.6 = 48eb9d8b6c26a9dfb317906d5099acabce8719c8
```

`main` is a moving production source branch and may contain later verified patches or docs-only checkpoints. Never equate `main` permanently with a tag. Before any live operation, read fresh daemon status and verify `daemon_version`, `self_revision`, repository registry identity and execution variant.

Production bounded-parallel execution uses `agent_parallel.py` with the repository registry and a hard worker cap of four. Serial `agent_multirepo.py` remains a fallback path, not the production dedupe path.

## Normal inspection order

1. Read `AGENTS.md` and `docs/CURRENT_HANDOFF.md`.
2. Read current `main` and relevant immutable release/checkpoint SHA.
3. Read fresh daemon status from the operational repository.
4. Read only the target repository status/task/result needed for the next decision.
5. For Chat Bridge work, read the exact conversation control record; do not infer current scheduling from an old chat.

## Executable repository work

- Resolve the actual target repository from the runtime catalog/registry.
- Require its exact canonical `agent_binding` in `.agent/tasks`.
- Keep executable effects deterministic and bounded.
- Declare required machine/hardware resources explicitly.
- Use one stable branch-scoped `dedupe_key` for one logical intent when cross-chat overlap is possible.
- Do not reuse the same explicit key for a materially changed corrective plan.
- Inspect pending/active/recent work before publishing another task.

Children and Superchat messages never bypass this path.

## Queue dedupe behavior

The production parallel worker suppresses equivalent queued work and recent duplicates before expensive execution. Suppression is terminal evidence (`duplicate_task_suppressed`) rather than a silently stranded task. Admission receipts are tied to durable claims; recovery of an interrupted/cancelled claim removes that active block. Completion receipts are intentionally short-lived.

If a task fails and a materially changed corrective plan is required, publish a new intent rather than blindly replaying the same explicit dedupe identity.

## Multi-repository / host operations

`host-ops` is the explicit `multirepo` host-operation/planning scope. Use it only for true host effects that belong there. A repository edit/build/test still belongs to the target repository and must use that repository's own binding and execution-enabled admission.

Never use `host-ops` to tunnel around a disabled target repository.

## Superchat live operation

At rest, keep Conversation Operator intake disabled unless an intentional campaign needs it. A live acceptance/campaign must:

1. verify the parent conversation and current Bridge control state;
2. verify the isolated child-browser/operator configuration;
3. explicitly enable only the supported operator path if required;
4. create bounded reasoning-only children;
5. keep execution authority in the parent -> target `.agent/tasks` boundary;
6. collect exact child registration/result/evidence;
7. retire/close owned child state when the bounded proof ends;
8. pause/disable campaign intake again unless continuing deliberately.

Do not fall back to repeated manual Chrome login/Cloudflare/DOM loops. Ambiguous auth/ownership is a stop condition, not a reason to weaken checks.

## Chat Bridge pacing/control

For GitHub-managed pacing use the exact `conversation_controls` record for that chat. Increment `control_generation` only for desired-state schedule mutations. `enabled=false` plus `next_wake_at=null` is the paused state. Never modify Bridge Master through per-conversation state.

## Release and checkpoint discipline

- Verify behavior-changing code on the exact candidate SHA before merge.
- Tags remain immutable release anchors.
- After merge, allow the guarded self-update path to advance production naturally; verify the exact installed `self_revision` rather than forcing a restart solely to obtain a new SHA.
- Docs-only checkpoint commits may advance `main` beyond a release/code checkpoint; record immutable anchors and read current `main` fresh.
- Keep only `main`, `chat-bridge-state`, `operator-control` and genuinely active short-lived work branches. Historical plans belong in history/evidence, not in current operational instructions.

## Current acceptance boundary

The next production activity is one bounded live Superchat acceptance on real code. It is not a broad fan-out, stress test or autonomous multi-goal campaign. Success means visible parent delegation, child reasoning evidence, parent synthesis and at most one justified real target execution without duplicate work.
