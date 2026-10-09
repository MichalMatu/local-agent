# Next live acceptance — controlled restart of an active Fabric campaign

**This is a specific operator-guided legacy DOM/Chrome acceptance test, not
the current GitHub-first Milestone 8 new-chat handoff.** For the latter, use
[GITHUB_FIRST_CURRENT_HANDOFF.md](GITHUB_FIRST_CURRENT_HANDOFF.md).
Do not run the active-campaign Chrome reload procedure just because a new
engineering chat has been opened.

Current as of 2026-10-08. This is an **operator-guided test plan**, not permission to launch tasks, change global Master state or automatically replay existing children.

## Prerequisites

Read `AGENTS.md`, `docs/conversation_fabric/CURRENT_PLAN.md` and [the verified 0.8.13 checkpoint](CHECKPOINT_2026-10-08_BRIDGE_0813_LIVE_ACCEPTANCE.md). Confirm freshly:

- the parent is the exact managed ChatGPT conversation in the normal authenticated Chrome session;
- installed Chat Bridge reports **0.8.13 / content v26**, Master and parent enabled;
- the previous `cf-a9f08cda8905ab33` and `cf-df084c77d84a5929` campaigns are terminal;
- no pending/undelivered terminal feedback or preexisting live campaign would be overwritten;
- the operator is ready to supervise **one** controlled extension/service-worker restart.

## Bounded exercise

1. Explicitly delegate **two** narrow reasoning-only children using one plain-text trailing `LOCAL_AGENT_CF` block; wait for worker admission evidence. No Local Agent tasks or GitHub state mutation.
2. Allow child tabs to open and ensure each submitted bootstrap is unique; **do not manually close** child tabs.
3. While a child is still working, have the operator reload the extension once. Leave child tabs open; do not force replay of the bootstrap.
4. Observe exact tab/transaction/request/bootstrap/current-URL claim recovery. If ownership is not provable, preserve the failure evidence and stop.
5. Wait for complete ASCII footer, repeated stable capture of each result, auto cleanup of exact owned tabs and one terminal parent feedback.
6. Check campaign/vault, no duplicated child submissions, no stale feedback/replay after the next worker wake. Record PASS / PARTIAL / FAIL with campaign ID, child IDs and observed popup state.

Historical failed campaign `cf-0c2fd2d492856bc8` was impacted by a malformed legacy footer and a manually closed child tab. Do **not** reopen or automatically repeat it.

## Exit

This experiment closes only the **live recovery** gap. It does not establish machine execution authority or certify unrelated Host Ops/Tool Runtime code. Existing Chromium CI provides bounded restart regressions; it is not this operator Chrome experiment. Return to `docs/CURRENT_HANDOFF.md` for the independent Milestone 7 Phase C implementation track.
