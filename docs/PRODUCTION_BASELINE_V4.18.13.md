# Local Agent v4.18.13 production baseline

This document freezes the known-working production baseline before the control-probe parallel-admission fix. It is intentionally historical: current candidate behavior belongs to v4.18.14 documentation.

## Exact rollback identity

- Release: `v4.18.13`
- Release source: `local_agent.version.RELEASE_VERSION == "4.18.13"`
- Commit: `a32e54858c3bcb9687334b3232b71ae6ff130208`
- Production branch at freeze time: `main`
- Rollback branch: `rollback/v4.18.13-known-working`
- Fix branch: `fix/control-probe-parallel-admission`
- Running production daemon reported the same `self_revision` and daemon version before this branch was created.

The annotated `v4.18.13` tag points to the exact commit above. The rollback branch is an additional human-readable pointer to the same commit.

## Freeze rule

Do not advance `main` for the scheduler fix until the exact v4.18.14 candidate has focused positive/negative regression coverage, the full verification matrix is green, macOS smoke includes the control-admission tests, downstream/current documentation has been audited, and the exact candidate diff has been reviewed.

Documentation and implementation work for this issue belongs on `fix/control-probe-parallel-admission` until release approval. Creating or updating this candidate branch must not trigger production self-update because production tracks `main`.

Do not restart or stop the production Local Agent merely to prepare or inspect the candidate.

## Known-working behavior

The v4.18.13 baseline is operational and executes repository tasks correctly when admitted. Repository identity, task binding, task/result durability, process lifecycle, resource locks, RSS watchdogs and the serial fallback remain intact.

Current production uses bounded parallel mode with `max_workers=4`; the scheduler hard cap is also 4. One repository still executes one repository turn at a time.

The registered project repositories use `resources: []` for executable work, including project-dedicated hardware operations. Device/port discovery is performed inside task commands. The generic Local Agent runtime still supports named resources and `resources: ["machine"]` for genuinely shared/global resources.

`memory_limit_mb` is a per-task process-group RSS watchdog. It is not a scheduler-wide memory reservation and does not prevent admission of another repository task based on aggregate host RAM.

## Known v4.18.13 admission defect

There is one confirmed production scheduling defect relevant to parallel work.

The first enabled repository is the supervisor control repository. While that repository has an active worker, the periodic global-control probe cannot acquire the same repository execution lease and returns `LEASE_BUSY`. After repeated lease-busy outcomes, v4.18.13 can switch to a global admission drain. While the drain is active, unrelated repository tasks are not admitted until the active worker set becomes empty.

This means a sufficiently long task in the control repository can temporarily collapse effective cross-repository parallelism even when every task has `resources: []` and worker capacity remains available.

This is not an RSS/memory admission limit and is not caused by the shared machine lock used by normal `resources: []` tasks.

## v4.18.14 candidate status

The candidate repair is implemented on `fix/control-probe-parallel-admission` and is versioned as v4.18.14. The authoritative finalized semantics are in `GOLDEN_STANDARD.md`, `MULTI_REPOSITORY.md`, `OPERATIONS.md` and `RELEASE_NOTES_V4.18.14.md`.

The repair:

- separates general control retry/backoff from the true consecutive-`LEASE_BUSY` streak;
- makes `DEFERRED` break that lease-busy streak;
- pauses only new control-repository admission after six consecutive known-worker `LEASE_BUSY` outcomes;
- leaves unrelated repositories admissible while that known worker continues;
- preserves the six-consecutive-busy defensive global drain for unexplained lease holders;
- preserves immediate drain for confirmed `PENDING` global control;
- resets stale control-admission evidence when the configured control-repository identity changes;
- places pure control-admission state/classification in `local_agent.supervisor.scheduling`, leaving `orchestrator.py` as the side-effect coordinator.

The candidate remains unshipped until explicitly merged/tagged and verified live.

## Required regression evidence for the fix

Before `main` advances, the exact final v4.18.14 SHA must prove all of the following:

1. Five consecutive `LEASE_BUSY` outcomes remain retry-only.
2. The sixth known-active-control-worker `LEASE_BUSY` pauses only new control-repository admission.
3. The sixth unexplained `LEASE_BUSY` retains bounded defensive global drain.
4. A `DEFERRED` probe breaks the consecutive lease-busy streak without removing bounded retry/backoff.
5. A second repository with `resources: []` can start while the control repository is still executing after the six-busy threshold has been crossed.
6. The real integration path logs the known-worker pause and not the global-drain path.
7. A confirmed pending global control request still stops new admission and drains safely.
8. `resources: ["machine"]` exclusivity/starvation prevention, inherited resource locks, repository isolation, hard binding and process-lifecycle tests remain unchanged/green.
9. Full compile/Ruff/unittest, coverage, Python 3.14, Bridge browser and macOS ARM64 smoke pass on the exact candidate SHA.
10. Current-documentation and release-metadata drift checks pass and downstream repository instructions do not contradict the candidate.

The short two-repository barrier integration test is insufficient by itself because it may complete before the supervisor control-probe path reaches the starvation threshold. The v4.18.14 suite therefore includes a dedicated long-lived control-repository overlap regression.

## Documentation audit

At freeze time, several canonical files still described historical worker counts or incomplete BUG-002 behavior. The v4.18.14 candidate corrects those current operational documents and adds automated drift checks that reject obsolete `--max-workers 2` commands/three-worker-cap claims in canonical current docs.

Historical release notes and this baseline are not rewritten to pretend v4.18.14 existed in the past. Where this document discusses the candidate, it does so explicitly as post-freeze status.

## Rollback procedure

The preferred rollback target remains the immutable tag `v4.18.13` or equivalent branch `rollback/v4.18.13-known-working`.

Before changing the production checkout, stop admission safely and ensure no important task is active. Preserve unexpected local changes instead of discarding them blindly. Then restore the production checkout to the exact baseline commit and verify:

```text
v4.18.13
= a32e54858c3bcb9687334b3232b71ae6ff130208
= rollback/v4.18.13-known-working
```

After rollback, verify the running `.agent/status/daemon.json` reports daemon version `4.18.13` and `self_revision` `a32e54858c3bcb9687334b3232b71ae6ff130208`, then verify one real queued repository task before considering rollback complete.
