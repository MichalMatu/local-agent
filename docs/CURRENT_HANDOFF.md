# Current handoff — Local Agent v4.19.11 checkpoint

Date: 2026-10-01

## Purpose

This is the continuation checkpoint for the Local Agent / Chat Bridge work after the 4.19.11 hardening pass. Read this first, then follow the canonical docs and exact GitHub evidence.

## Current release state

- Candidate: Local Agent 4.19.11 / Chat Bridge 0.6.2
- Candidate branch: work/checkpoint-v4.19.11
- Release PR: #122
- Base: main
- Candidate runtime checkpoint before this documentation pass: 104e370d9f58fdd1b94a0911b9f402ef919533a7
- Runtime schema: 3
- Content protocol: 13
- Assistant guard: 8
- Production baseline before merge: Local Agent 4.19.10 / Chat Bridge 0.6.1

## What is proven

The checkpoint repaired the GitHub reconciliation regression that could resurrect a deliberate local terminal stop. It also added the combined repository/resource orphan-lock regression, made coverage a 70% CI gate, pinned GitHub Actions to immutable revisions and refreshed release metadata.

The exact candidate passed the canonical CI matrix, including compile/Ruff/full unit and integration suite, coverage, Python 3.14, real Chromium extension smoke and macOS smoke.

The bounded live browser gate was exercised from the normal Chrome/Chat Bridge installation. A short one-minute control interval successfully drove the Bridge wake path. The conversation was returned to the canonical PAUSED state afterwards.

The final desired state on chat-bridge-state is deliberately disabled with no one-shot deadline. Do not leave the release test conversation armed while doing merge/release work.

## Architecture decision

```text
Superchat / ordinary ChatGPT reasoning
          |
          v
GitHub control + evidence
          |
          v
Local Agent deterministic orchestration/execution
          +--> host-ops deterministic tools
          +--> narrow ChatGPT Browser Driver
```

Do not introduce a second control plane. MCP and direct OpenAI API model execution are excluded from the current target architecture.

Chat Bridge remains only as a bounded browser lifecycle/transport layer. GitHub is the authority for managed schedule/status state. DOM observations are transport evidence only.

## Documentation map

1. AGENTS.md — normative repository rules.
2. docs/GOLDEN_STANDARD.md — release/runtime invariants.
3. docs/DEVELOPMENT_PLAN.md — current product direction and next milestone.
4. docs/CHECKPOINT_AUDIT_V4.19.11.md — detailed audit and residual risks.
5. docs/GITHUB_BRIDGE_CONTROL.md — GitHub desired-state contract.
6. docs/AUTONOMOUS_CHAT_LOOP.md — planner continuation discipline.
7. docs/superchat/ROADMAP.md — longer-term lifecycle roadmap.

## Branch state

Keep main, chat-bridge-state, operator-control and develop/conversation-fabric.

Delete after the release is actually established:

- work/checkpoint-v4.19.11

No other current branch is an obsolete disposable work branch. Conversation Fabric is intentionally long-lived; the two state/control branches are operational and must not be deleted.

## Release completion sequence

1. finish this documentation checkpoint;
2. run exact-SHA CI on the resulting candidate;
3. review PR #122 one final time;
4. explicitly merge #122 into main;
5. tag the released main commit as v4.19.11;
6. verify the installed ~/local-agent checkout from main;
7. validate live daemon revision/version and a harmless real task/status path;
8. delete work/checkpoint-v4.19.11;
9. leave the release conversation PAUSED;
10. begin new work only from develop/conversation-fabric.

## Next development action

After release cleanup, continue on develop/conversation-fabric with the existing Stage 8 first-live gate: exactly one real dedicated-profile ChatGPT child through seed -> prepare -> login -> arm -> run, requiring canonical child registration and durable completion evidence before adding adoption/terminal/retirement.

Do not start the 44-node campaign. Do not enable a production child scheduler. Do not create a second executor.

## Recovery rule

If a future conversation is unsure where to continue, this handoff plus docs/DEVELOPMENT_PLAN.md are the current checkpoint tie-breaker. Exact GitHub task/run/result/control evidence always outranks remembered chat context.
