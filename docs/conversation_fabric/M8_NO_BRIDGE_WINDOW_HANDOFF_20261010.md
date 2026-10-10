# M8 no-Bridge Conversation Fabric — window handoff (2026-10-10)

**Current source-of-truth continuation for the next ChatGPT conversation.**
This note supersedes the 2026-10-09 "current" section of
`GITHUB_FIRST_CURRENT_HANDOFF.md` for this specific source-only track.
Treat all commit identifiers as observations: refresh GitHub before action.

## Mission and strict operator constraints

Continue `MichalMatu/local-agent`, Milestone 8: GitHub-first Conversation
Fabric **manual, synthetic-only, read-only review and evidence workflows**.
Work entirely within the new conversation using the GitHub connector and the
canonical Mac Local Agent when execution is genuinely necessary.

- **Do not** use Chat Bridge (under migration), Codex or its credits,
  GitHub Actions, subchat delegation, or the legacy browser bridge to
  schedule tasks.
- **Do not** modify `main`, `interface/**`, installed daemon code,
  global agent configuration, or restart the Local Agent.
- **Do not** enable automatic ChatGPT Send/ACK, task replay, real/private
  migration, old-transport retirement, same-parent takeover, or global
  effect authority. Synthetic read-only proofs do not establish these gates.
- Keep stacked PRs **draft and unmerged**. Do not change the SHA of a
  source branch while an exact-head Mac test is running.
- Use deterministic, bounded, fail-closed source/evidence validation.
  Source, docs, commits, tasks and shell-visible machine output are
  English-only per `AGENTS.md`; conversational replies may be Polish.

## Verified current GitHub and Mac state — 2026-10-10

- Public repository: `MichalMatu/local-agent`.
- Observed `main`: `76865cbc7d92861998e8e33a96193d95c120fe02`;
  unchanged by this track.
- Draft chain **#243 through #258**, all 16 PRs OPEN/DRAFT and unmerged.
  Each PR is based on the previous PR's work branch, not on `main`.
- **Latest code PR #258**:
  `https://github.com/MichalMatu/local-agent/pull/258`
  branch `work/m8-public-read-session-budget-20261010`,
  exact head `d328505d7c055d31e5aa5855bff2b11430fe841b`.
  Current handoff branch was derived from this exact head and only
  documents continuity; it is **not** a new tested code head.
- Canonical `local-agent` binding:
  `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`. Observed
  `agent-control/.agent/status/daemon.json`: **idle**, no active task,
  last observed update `2026-10-10T03:20:06.706874+00:00`.
  Always independently confirm binding in the execution catalog,
  `agent-control/.agent/binding.json`, and fresh daemon status before
  publishing tasks.
- Last code delta #258: anonymous, fixed-repository GitHub GET client
  with per-session maximum **52 requests, 8 MiB responses, 120 s**,
  synchronized shared budget; no redirect, credentials, arbitrary
  endpoints or write methods. Aggregate time is an acceptance deadline
  and a clipped request timeout, **not** an OS-level preemption proof.

## Durable, exact-head Mac evidence

All receipts are under
`agent-control/.agent/results/<task_id>.json`; **read receipt fields**,
not just task publication or daemon heartbeat:

1. **#258 exact head `d328505...`**
   - `local-agent-m8-pr258-public-session-budget-focused-20261010-v2`:
     **89/89 Python tests PASS**, compile PASS, Ruff PASS, exit 0.
   - `local-agent-m8-pr258-full-local-20261010-v1`:
     **1046/1046 Python tests PASS**, core branch coverage **83.8%**,
     full `verify_local.py --profile full` PASS, exit 0,
     finished `2026-10-10T03:19:24.661036+00:00`.
   - `local-agent-m8-pr258-real-get-budget-20261010-v1`:
     **PASS**, actual anonymous public GitHub GET of one existing,
     separately pinned task/result (no bearer token), redacted
     deny-only review, exit 0, finished
     `2026-10-10T03:19:54.130712+00:00`.
   - Earlier focused v1 failed on the old `oversized` error message
     when introducing session budgets. That failure is retained.
     The v2 source fixes it without changing the limits.
2. **#257 head `89f999539b97364b4e9ab113c52ce12833a57dac`**
   - Focused **82/82 PASS**, compile and Ruff PASS;
     real anonymous GitHub stage-correlation smoke PASS.
   - First full suite **FAILED** with one teardown error in
     `tests.test_lease_recovery`:
     `RuntimeError: cannot reset process lifecycle with live processes`.
     Isolated `test_lease_recovery` module **11/11 PASS**.
   - Separate, explicitly operator-published full confirmation
     `local-agent-m8-pr257-full-confirmation-20261009-v2`:
     **1039/1039 PASS**, **83.8%** coverage, exit 0. Do not erase the
     original failure or assume process test stability is proven.
3. **#255** full **1037 PASS**, **83.8%** coverage, real pinned GET PASS.
   **#254** full **1034 PASS**, **83.7%**, real anonymous GET PASS.
   **#253** full **1023 PASS**, **83.7%**, plus focused PASS.
   Earlier PR exact-head evidence lives in their PR bodies and receipts.

## Implemented source-only capabilities

- Strict manual **new-parent** synthetic observation and portable handoff
  with independent caller-supplied SHA; both are review-only.
- Public/private approved-fixture GitHub GET recovery; no private/live
  arbitrary prompt recovery and no browser effects.
- Commit/tree/file/digest-pinned `agent-control` task/result reconciliation,
  redaction, stage identity correlation and distinct incomplete-evidence
  outcome for otherwise successful truncated logs.
- Deterministic **non-published** Mac test-task planning; optional,
  explicitly approved temporary pinned test dependencies.
- `python -m scripts.no_bridge_manual` commands:
  `export`, `inspect`, `plan-test`, `verify-github`, `status-github`.
  Network operations are default-denied; anonymous public mode requires
  both `--anonymous-public-read` and `--allow-readonly-network`.
  The CLI does not Send/ACK, publish tasks or restart the daemon.
- Exact latest source: `local_agent/conversation/github_fabric_agent_control_public_rest.py`.
  Related tests: `tests/test_github_fabric_agent_control_public_rest.py`.

## Open gates and sensible next actions

1. Refresh GitHub current `main`, PR #258, this handoff PR, canonical
   binding and daemon. Read #258 full/focused/live smoke receipts above.
2. **Do an independent-style static security/integration assessment** of
   exact code with bounded API parsing, concurrent session accounting,
   URL/request restrictions and report redaction. A self-review is
   useful but **cannot be represented as an independent approval**.
   Do not create more changes unless a specific, reproducible defect
   warrants a separate draft stacked on the current code head.
3. Evaluate the observed intermittent process lifecycle teardown failure
   separately from new no-Bridge source; do not restart the daemon or
   kill processes on the basis of one historical flake.
4. If more code work is justified, preserve one immutable branch per
   candidate, run focused exact-head Mac tests first, then a full profile
   with a temporary virtualenv per `LOCAL_VERIFICATION.md`, and inspect
   `.agent/results/` before saying PASS.
5. The **non-negotiable blockers** for any real Chrome/ChatGPT automated
   Send/ACK or same-parent takeover are trusted effect-time fencing of
   old/offline uncooperative extensions and independent security/
   integration approval. GitHub CAS, a JavaScript receipt, a verified
   source commit or a manifest digest **do not** establish global
   exclusion of uncooperative clients. Keep all such effects disabled.

No merge, production activation, daemon restart, Chat Bridge, Codex,
GitHub Actions or background automation was done as part of this handoff.
