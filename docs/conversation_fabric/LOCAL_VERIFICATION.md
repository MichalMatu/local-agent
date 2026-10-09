# Exact-head local verification (Mac / isolated sandbox)

**Operator mode since 2026-10-09:** GitHub Actions automatic CI is disabled.
The checked-in workflow is `workflow_dispatch` only. Do not dispatch it or
require hosted checks for acceptance until the operator explicitly changes
this decision. GitHub remains the **source/evidence/PR** plane; only hosted
Actions execution is excluded. Preserve `agent-control` Local Agent tasks.

## Required evidence

For each candidate source SHA, inspect the current branch, exact PR head and
daemon first. Route executable Mac tasks only to the canonical
`MichalMatu/local-agent` repository using the exact binding confirmed
against its `agent-control/.agent/binding.json`, runtime catalog and daemon.
Read-only task commands MUST begin with an exact
`test "$(git rev-parse HEAD)" = "<EXPECTED_SHA>"` check. Do not run
unbounded commands, change the installed daemon checkout, or restart
the agent just to run tests. Use isolated repository work branches/worktrees.
For each result, retain task ID, branch, source SHA, command, exit status,
bounded output and runtime/tool versions under the repository's durable
`.agent/results/` contract. An absent/timeout/unconfirmed result is not PASS.

## Local acceptance matrix

Run each relevant group on the *same exact candidate head*, using
`python` bound to the tested interpreter. Each failed step blocks merge.
An unavailable interpreter, Playwright, or host permission is recorded as
**unverified**, not substituted by another passing check.

| Concern | Commands / evidence |
| --- | --- |
| Python compile + Ruff + bridge syntax/Node unit | `python scripts/verify.py --only compile`, `--only lint`, `--only bridge` |
| Python unit/integration | `python scripts/verify.py --only tests` |
| Native Mac/process/supervisor | `python scripts/verify.py --profile macos-smoke` on Mac for runtime-impacting changes |
| Isolated Chromium extension/DOM restart | `python scripts/verify.py --profile bridge-browser` where local Playwright/Chromium are installed; no real chat Send |
| Absorbed Host Ops architecture + design | `python scripts/host_ops_quality/check_architecture.py` and `python scripts/host_ops_quality/check_design.py` |
| Host Ops behavior/branch coverage | `python -m pytest -q --cov=local_agent.host_ops --cov-branch --cov-fail-under=85 host_ops_tests` with local pinned test dependencies |
| Local Agent core branch coverage | `coverage run --omit='local_agent/host_ops/*' -m unittest discover -q`; `coverage report --fail-under=70 -m` |
| Python 3.14 compatibility | Run `python3.14 scripts/verify.py --only tests` **only if installed** and dependencies available; otherwise mark unverified |
| Changed feature regression | Exact negative/restart/race tests affected by the diff (e.g. parent-fence Python and private reader JS) |
| Operator/browser acceptance | Real authenticated extension tests only with explicit operator authority, separate from isolated fixture test PASS |

Python `pytest`, `pytest-cov`, `coverage`, `ruff` and Playwright must already be
locally available or installed by an explicitly authorized, bounded setup.
Never silently fetch an unpinned dependency or write browser credentials.
The operator is not required to provision paid cloud runners.

## PR and integration gates

1. Re-read `main`, the PR head, its base and actual changed paths. No branch
   SHA inferred from past notes can authorize tests or merges.
2. Run focused tests first, then the applicable full matrix above on that
   exact SHA. Mac results may replace hosted OS checks only for the executed
   coverage, not Python versions or environments that did not run.
3. Keep original independent security and integration reviews where
   specified. In particular, parent-fence #209 and #214 remain draft until
   the missing review evidence is obtained and shared old/offline DOM
   admission and no-replay requirements are addressed as instructed.
4. An exact-head PASS may authorize a merge only when every required local
   test and independent acceptance gate is met. Recheck the head immediately
   before merge, retain the durable result and perform a non-force merge.
5. A cancelled or queued historical GitHub Actions run means **nothing**
   about source correctness. Do not wait, rerun, manually dispatch or count
   it as PASS. Existing queued historical runs may require operator-side
   cancellation if the connected GitHub app does not expose a cancel API.

No private GitHub-first Send or real ACK authorization, no automatic
Superchat-to-Superchat promotion, no global Bridge Master change, no
implicit replay or receipt pruning. Durable unresolved receipts are preserved.
