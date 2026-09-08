# Local Agent v4.18.13 production baseline

This document freezes the known-working production baseline before the control-probe parallel-admission fix.

## Exact rollback identity

- Release: `v4.18.13`
- Release source: `local_agent.version.RELEASE_VERSION == "4.18.13"`
- Commit: `a32e54858c3bcb9687334b3232b71ae6ff130208`
- Production branch at freeze time: `main`
- Rollback branch: `rollback/v4.18.13-known-working`
- Fix branch: `fix/control-probe-parallel-admission`
- Running production daemon reported the same `self_revision` and daemon version before this branch was created.

The annotated `v4.18.13` tag already points to the exact commit above. The rollback branch is an additional human-readable pointer to the same commit.

## Freeze rule

Do not advance `main` for the scheduler fix until the candidate branch has focused regression coverage, the full required verification gates are green, and the exact candidate diff has been reviewed.

Documentation and implementation work for this issue belongs on `fix/control-probe-parallel-admission` until release approval. Creating or updating this candidate branch must not trigger production self-update because production tracks `main`.

Do not restart or stop the production Local Agent merely to prepare or inspect the candidate.

## Known-working behavior

The v4.18.13 baseline is operational and executes repository tasks correctly when admitted. Repository identity, task binding, task/result durability, process lifecycle, resource locks, RSS watchdogs and the serial fallback remain intact.

Current production uses bounded parallel mode with `max_workers=4`; the scheduler hard cap is also 4. One repository still executes one repository turn at a time.

The registered project repositories currently use `resources: []` for executable work, including their project-dedicated hardware operations. Device/port discovery is performed inside task commands. The generic Local Agent runtime still supports named resources and `resources: ["machine"]` for genuinely shared/global resources.

`memory_limit_mb` is a per-task process-group RSS watchdog. It is not a scheduler-wide memory reservation and does not prevent admission of another repository task based on aggregate host RAM.

## Known v4.18.13 admission defect

There is one confirmed production scheduling defect relevant to parallel work.

The first enabled repository is the supervisor control repository. While that repository has an active worker, the periodic global-control probe cannot acquire the same repository execution lease and returns `LEASE_BUSY`. After six consecutive lease-busy probe outcomes, v4.18.13 intentionally switches to a global admission drain. While the drain is active, unrelated repository tasks are not admitted until the active worker set becomes empty.

This means a sufficiently long task in the control repository can temporarily collapse effective cross-repository parallelism even when every task has `resources: []` and worker capacity remains available.

This is not an RSS/memory admission limit and is not caused by the shared machine lock used by normal `resources: []` tasks.

The candidate fix must preserve defensive handling for genuinely unexpected/orphaned control-repository lease contention while treating lease ownership by the supervisor's own known active control-repository worker as an expected condition that must not drain unrelated admission.

## Required regression evidence for the fix

The candidate must prove all of the following before `main` advances:

1. An active control-repository worker plus a control probe returning `LEASE_BUSY` does not set a global drain merely because that known worker owns the lease.
2. A second repository with `resources: []` can start and run while the control repository is still executing a long task.
3. Unexpected control-repository lease contention without a corresponding known active worker retains bounded defensive retry/drain behavior.
4. A confirmed pending global control request still stops new admission and drains safely.
5. `resources: ["machine"]` exclusivity and its starvation-prevention behavior remain unchanged.
6. Existing resource-lock inheritance, repository isolation, hard binding and process-lifecycle tests remain green.
7. The full repository verifier and the macOS parallel smoke profile pass on the exact candidate SHA.

The existing short two-repository barrier integration test is insufficient by itself because it completes before the 15-second supervisor control-probe interval can expose this defect. Add a long-lived control-repository overlap regression.

## Documentation audit at freeze time

The implementation and release tag are consistent at v4.18.13, but canonical documentation contains stale concurrency text that must be corrected on the candidate before release:

- `README.md` still recommends two workers and states an obsolete hard cap of three.
- `docs/OPERATIONS.md` still uses `--max-workers 2` in production/deployment examples.
- `docs/MULTI_REPOSITORY.md` still states production two workers and hard cap three.
- `docs/GOLDEN_STANDARD.md` still states two workers and hard cap three.
- `AGENTS.md` has the correct hard cap of four but still calls two workers the recommended production value.
- `docs/CHANGELOG.md` does not yet contain a v4.18.13 entry even though the release is tagged.
- `docs/RELEASE_NOTES_V4.18.13.md` correctly records a four-worker render regression and hard-cap correction, but its heading still says `candidate` although v4.18.13 is released.

Correct these on the candidate branch together with the scheduler fix so the final release documentation describes the actual production configuration and fixed control-probe semantics. Do not make documentation-only commits to `main` before candidate validation, because production self-update tracks `main` revisions.

## Rollback procedure

The preferred rollback target is the immutable tag `v4.18.13` or the equivalent branch `rollback/v4.18.13-known-working`.

Before changing the production checkout, stop admission safely and ensure no important task is active. Preserve any unexpected local changes instead of discarding them blindly. Then restore the production checkout to the exact baseline commit and verify:

```text
v4.18.13
= a32e54858c3bcb9687334b3232b71ae6ff130208
= rollback/v4.18.13-known-working
```

After rollback, verify the running `.agent/status/daemon.json` reports daemon version `4.18.13` and `self_revision` `a32e54858c3bcb9687334b3232b71ae6ff130208`, then verify one real queued repository task before considering rollback complete.
