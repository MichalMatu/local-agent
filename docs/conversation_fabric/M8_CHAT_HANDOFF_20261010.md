# Milestone 8 — no-Bridge new-chat continuation handoff (2026-10-10)

**Status: verified source-only checkpoint, NOT production migration.** This is
the newest continuation entrypoint for the current stacked no-Bridge track,
superseding older "current" sections in
`docs/conversation_fabric/GITHUB_FIRST_CURRENT_HANDOFF.md`. All identifiers
are observed checkpoints; query GitHub again before making decisions.

## Exact current checkpoint

- Repository: `MichalMatu/local-agent`.
- `main` SHA observed: `76865cbc7d92861998e8e33a96193d95c120fe02`
  (untouched by this track).
- Latest **tested source head**: PR **#258** (open DRAFT), branch
  `work/m8-public-read-session-budget-20261010`, exact SHA
  `d328505d7c055d31e5aa5855bff2b11430fe841b`. Base PR #257 branch
  `work/m8-stage-evidence-correlation-20261009`, SHA
  `89f999539b97364b4e9ab113c52ce12833a57dac`.
- Earlier documentation-only continuity PR #256 was stacked on #255.
  Entire chain #243–#258 remains intentionally draft/unmerged. Check each
  open/draft status and parent lineage afresh, do not assume GitHub PR order
  is a merge permission.
- The **handoff branch** `work/m8-chat-handoff-20261010` is created from
  the already tested #258 head and changes documentation only. Any handoff
  PR is **not** a new exact-head code test; do not replace #258 evidence
  with the handoff commit SHA.
- Canonical Mac Local Agent binding:
  `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`, independently checked against
  `agent-control/.agent/binding.json` and the daemon binding.
- At last observation `agent-control/.agent/status/daemon.json`:
  `state=idle`, `current_task_id=null`, timestamp
  `2026-10-10T03:30:23.419950+00:00`. Treat as ephemeral.

## Verified terminal evidence — do not repeat these tests by default

| Source head | Scoped test task under `agent-control/.agent/results/` | Terminal result |
| --- | --- | --- |
| #258 `d328505d...` | `local-agent-m8-pr258-public-session-budget-focused-20261010-v2.json` | 89/89 Python unit tests PASS, compile + Ruff PASS, exit 0 |
| #258 `d328505d...` | `local-agent-m8-pr258-full-local-20261010-v1.json` | 1046/1046 tests PASS; core branch coverage 83.8%; full profile terminal PASS, exit 0 |
| #258 `d328505d...` | `local-agent-m8-pr258-real-get-budget-20261010-v1.json` | PASS on an actual anonymously fetched, commit-pinned public GitHub task/result; only redacted deny-only review metadata, no bearer token |
| #257 `89f99953...` | `local-agent-m8-pr257-full-local-20261009-v1.json` | First full run **FAILED**: one teardown error in unrelated `tests.test_lease_recovery` (live process lifecycle). Preserve this incident |
| #257 `89f99953...` | `local-agent-m8-pr257-lease-isolation-20261009-v1.json` | Isolated lease-recovery module 11/11 PASS |
| #257 `89f99953...` | `local-agent-m8-pr257-full-confirmation-20261009-v2.json` | Separate manually published full run **1039/1039 PASS**, 83.8% coverage |

The first PR #258 focused attempt, pinned to a superseded head, also
failed due to changed error wording; fixed on #258's current head and
reverified in v2. Do not discard failed receipts or conflate rerun with
proof that an intermittent infrastructure test problem cannot recur.

## Implemented, source-only capabilities

- Default-denied manual/synthetic **new-parent** observation and portable
  canonical handoff: bounded strict JSON and independently supplied pins.
- Redacted GET-only source recheck through existing GitHub readers, and
  a pinned `agent-control` history index with commit/tree/blob identity
  checks and exact task/result digest/command/stage correlation.
- Review outcomes differentiate coherent reported PASS, reported nonpass,
  missing/unconfirmed receipt, and **incomplete evidence** (e.g. a
  successful command whose log was truncated).
- Offline operator CLI `python -m scripts.no_bridge_manual` provides
  `export`, `inspect`, and non-published `plan-test`; explicit
  `verify-github` and `status-github` are GET-only, operator opted-in.
- Explicit `status-github --anonymous-public-read --allow-readonly-network`
  hardcodes the public repo and four pinned GET path patterns; it ignores
  ambient bearer tokens, refuses redirects, caps per-response payloads.
- #258 extends that adapter with session-wide **52 GET attempts / 8 MiB /
  120 seconds**; on exhaustion it fails without a partial positive result.
  The deadline governs acceptance and socket timeout clipping, **not**
  an OS-level guarantee of hard-canceling a blocked DNS/proxy syscall.
- Tests and the actual GitHub smoke confirm reporting remains
  `operator_review_only` with no authenticated Mac execution attestation,
  no automatic retry, no dispatch or browser Send/ACK permission.

## Non-negotiable operating boundaries

1. Work **only in the current chat**, using the GitHub connector and
   **canonical Local Agent on the Mac** for authorized local checks.
   Chat Bridge remains broken/in migration: **do not use it**.
   No subchat delegation, no Codex or its credits, no GitHub Actions.
2. **Do not touch `main`**, do not merge draft PRs, and do not modify
   `interface/**` or unrelated application code.
3. Never restart the Local Agent or alter its daemon/global settings.
   Do not kill processes or make machine-wide environment changes.
4. For a Mac test task independently recheck the current canonical
   `agent_binding`, enabled repository execution catalog, daemon state,
   exact draft work branch and SHA; publish a bounded, clean-checkout-
   guarded `allow_write=false`, `resources=[]` task via the existing
   `agent-control` transport **only when necessary**.
   Prefer reading already durable test receipts over rerunning expensive
   full suites. Preserve failures as evidence.
5. No live private conversation migration, same-parent takeover,
   automatic browser Send/ACK, autonomous task retry or global legacy
   worker retirement. The absence of a trusted effect-time exclusion
   mechanism for old/offline Chrome extension instances is **unresolved**.
   Do not simulate completion with a GitHub SHA/lease, an operator flag
   or a synthetic fixture.
6. Independent security/integration review and production acceptance
   remain unfulfilled. Keep new work in a new stacked draft PR; do not
   enable execution effect authority.

## Recommended actions in the next chat

1. Read this handoff, current `AGENTS.md`,
   `docs/conversation_fabric/GITHUB_FIRST_CURRENT_HANDOFF.md`, and
   the latest #258 PR/body/code; query latest `main`, daemon state and
   exact PR chain. Prefer actual GitHub state over this static checkpoint.
2. Inspect the exact #258 terminal reports listed above and #257's
   recorded first-fail/second-pass lifecycle flake. Confirm that no
   pending Mac tasks need intervention.
3. Conduct a **read-only threat review** of public anonymous GET
   session budgets and stage/digest/commit checks, and the unresolved
   global old/offline Chrome worker exclusion. Note what cannot be
   proven; do not turn this into Send/ACK automation.
4. If a concrete source-only defect is found, fix it on a *new*
   work branch stacked on latest #258 (or latest docs-only handoff)
   and create a DRAFT PR; validate its exact head with focused tests
   and only necessary full Mac verification.
5. Update this source-of-truth handoff, PR evidence and outstanding
   blocker list before any subsequent context-window transfer.

## Do not confuse validation layers

GitHub object identity and task digest are **reported artifact integrity**,
not signed provenance or proof of Mac command effects. A task's
`allow_write=false` is a declaration, not a shell sandbox. Truncated
command output yields incomplete evidence, not failed execution or a
license to replay. The new-parent path is synthetic-only and strictly
manual. An independently authenticated old-worker quarantine/fencing
mechanism remains an external prerequisite for any real effectful
conversation transport migration.
