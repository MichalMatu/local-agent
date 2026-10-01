# Local Agent bug backlog

This file tracks confirmed or strongly evidenced Local Agent defects that still need engineering or release work.

`CHANGELOG.md` records release-target/shipped changes. This backlog records **known problems, candidate state and closure evidence** until a defect is released and verified.

## Workflow

For every newly discovered bug, record:

- a stable bug id and priority;
- observed symptoms and reproduction evidence;
- user/operator impact;
- the most likely technical cause, clearly marked when not yet proven;
- the intended repair direction;
- regression tests required before closing the item.

When a bug is fixed:

1. keep the backlog entry, mark it `Fixed`, and add the fixing commit/release;
2. add the shipped behavior change to `CHANGELOG.md` / release notes as appropriate;
3. retain regression coverage so the same failure cannot silently return.

A green candidate branch is not yet `Fixed` when production `main` has not advanced. Use `Candidate validated` until merge/tag/live verification completes.

Priorities:

- **P0** — safety/data-integrity failure or uncontrolled execution risk;
- **P1** — blocks normal Local Agent operation or requires disruptive manual recovery;
- **P2** — degraded reliability/usability with a practical workaround;
- **P3** — minor defect or hardening opportunity.

---

## BUG-001 — orphan descendant can retain `machine` / resource flock after worker failure

**Status:** Fixed in production source; released in v4.18.5, closure revalidated by the v4.19.11 checkpoint  
**Priority:** P1  
**First confirmed:** 2026-09-06  
**Area:** parallel supervisor, process lifecycle, resource admission, cancellation/recovery

### Original symptom

A repository task running Playwright/Vite became stuck. A surviving descendant retained inherited execution/resource lease descriptors after its worker disappeared, so later work could remain indefinitely in `waiting_resource`. A normal Local Agent restart did not reliably recover the host and the observed incident required a macOS reboot.

### Root cause and safety constraint

Local Agent intentionally inherits both repository execution leases and requested machine/named-resource `flock` descriptors into command descendants. This prevents worker death from creating unsafe overlapping execution, but it also means a detached descendant can keep both leases alive after its worker exits.

The kernel-held `flock`, not the lock-file pathname, is the exclusion mechanism. Deleting/recreating lock files is therefore never a valid recovery strategy and could allow unsafe overlap.

### Implemented repair

Release v4.18.5 moved orphan recovery into the guarded production entrypoint. With the global daemon lifecycle lock held and no live supervisor allowed to race recovery, Local Agent:

1. probes the configured repository leases;
2. identifies processes that actually hold those kernel locks (`/proc` fdinfo on Linux; `lsof` fileglob/current-lock evidence on macOS);
3. excludes the guarded process, its parent and init;
4. sends bounded `SIGTERM`, then `SIGKILL` only to proven holders that survive;
5. verifies that no holder remains and that the repository lease is actually acquirable before starting new execution.

The guarded entrypoint also watches a live supervisor that reports quiescent while repository leases remain busy. After the bounded stall window it recycles that supervisor and performs the same guarded orphan recovery. Recovery never targets broad executable names such as `node`, `vite`, `chromium` or `playwright`.

Because command descendants inherit repository and resource descriptors through the same registered spawn path, an orphan retaining `machine` or a named resource also retains the repository lease used to identify that exact holder. Killing the proven orphan closes the inherited resource descriptors with the process.

### Regression coverage and closure evidence

- `tests/test_lease_recovery.py::LeaseRecoveryTests.test_orphan_recovery_kills_only_actual_lock_holder` creates a real inherited repository `flock`, keeps an unrelated observer of the same lock path alive, requires recovery to terminate only the actual lock holder, and verifies reacquisition.
- `tests/test_lease_recovery.py::LeaseRecoveryTests.test_orphan_recovery_releases_inherited_resource_lock` reproduces the historical combined condition: a child inherits both a repository lease and a separate resource flock after the parent closes its copies; guarded repository-lease recovery must terminate that exact child and make **both** locks reacquirable.
- `tests.test_lease_recovery` is part of the canonical macOS smoke profile. The exact v4.19.11 checkpoint SHA `5103272ed9e44f46abc4eec12d9947d4404b8137` passed the full Linux suite, Python 3.14 compatibility, coverage gate, real Chromium Bridge smoke and macOS smoke with this combined lease regression present.
- `RELEASE_NOTES_V4.18.5.md` records the reproduced detached-daemon lease incident and shipped guarded recovery; `RELEASE_NOTES_V4.18.6.md` subsequently treats orphaned repository-lease recovery as fixed in v4.18.5.

### Safety invariants retained

- never delete/recreate lock files to recover a held lease;
- never kill by broad process name;
- never perform destructive orphan recovery while another Local Agent daemon owns the lifecycle boundary;
- verify actual lease release before allowing new execution;
- interrupted claimed work remains terminal/fail-closed and is never silently replayed.

The old backlog entry remained marked Open after the implementation shipped. The v4.19.11 checkpoint audit supplied the missing combined repository+resource regression proof and closes that documentation debt. A future distinct reproducer that can retain only a resource lock while no identifying repository lease remains would be a new defect, not a reopening of this incident without evidence.

---

## BUG-002 — active control-repository lease contention drains unrelated parallel admission

**Status:** Fixed in production source; introduced in v4.18.14 behavior and retained by later releases  
**Priority:** P1  
**First confirmed:** 2026-09-08  
**Area:** parallel supervisor, global control probe, repository admission

### Symptom

A long task in the supervisor control repository runs with `resources: []`, while another repository has a valid pending task with `resources: []` and unused worker capacity. Under v4.18.13, the second repository may remain unstarted for minutes and then begin shortly after the control-repository task finishes.

This makes production appear as if another repository is "holding the whole agent" even though neither task requested `machine` or a conflicting named resource.

### Evidence / reproduction

The v4.18.13 supervisor probes the designated control repository periodically while workers are active. The probe tries to acquire that repository's execution lease. When the control repository itself has an active worker, that worker correctly owns the same lease, so the probe returns `LEASE_BUSY`.

After repeated lease-busy outcomes, v4.18.13 can enter global control pending/drain state. While that state is active and any worker is still running, the main loop continues before normal repository admission. Unrelated repository tasks are therefore not started until the active worker set becomes empty.

Production evidence confirmed the pattern with the then-LiteGraph control repository and the then-Growbox waiting repository. Both tasks used `resources: []`; worker capacity was available; the waiting repository task started only after the long control-repository task ended.

The original short two-repository parallel barrier test did not expose the defect because it finished before the global-control probe/backoff path could accumulate enough lease contention.

### Impact

- cross-repository parallelism could collapse during sufficiently long control-repository tasks;
- pending tasks could wait well beyond the nominal repository poll interval despite free worker capacity;
- operators could misdiagnose the delay as RAM pressure, `machine` contention or a dead poll loop;
- production `max_workers=4` was not reliably usable for ordinary independent work on v4.18.13;
- development throughput was materially degraded.

### Non-cause: RAM admission

`memory_limit_mb` is not a scheduler-wide reservation. It is enforced inside an already-running task by process-group RSS sampling. The parallel supervisor does not sum task memory limits and does not block another repository because aggregate host RAM or requested per-task memory exceeds a scheduler threshold.

### Implemented repair

The repair introduced with v4.18.14 behavior lives in the existing scheduling ownership boundary instead of adding another state machine to `orchestrator.py`:

1. `local_agent.supervisor.scheduling.ControlDeferralState` owns control retry/admission evidence.
2. Overall deferred-probe count drives bounded 2-15 second retry/backoff; a separate **consecutive `LEASE_BUSY`** streak drives lease-starvation protection.
3. A `DEFERRED` sync/network/ACK-read outcome breaks the lease-busy streak while retaining bounded retry behavior.
4. Fewer than six consecutive `LEASE_BUSY` outcomes retry without changing admission.
5. On the sixth consecutive `LEASE_BUSY`, a known active control-repository worker causes only **new control-repository admission** to pause. Existing workers continue and unrelated repositories remain admissible when capacity/resources permit it.
6. That pause gives the supervisor a control-probe opportunity after the active control worker releases the lease, preventing a continuous control-repository queue from starving global control.
7. Six consecutive `LEASE_BUSY` outcomes with no corresponding known active control worker retain the defensive global drain for unexplained/stale lease ownership.
8. A confirmed `PENDING` global control request still drains immediately.
9. A configured control-repository identity change clears stale retry/lease-busy/pause evidence and invalidates the previous control-poll clock.
10. `resources: ["machine"]` priority/drain semantics, named-resource locking, repository leases, claims/results, hard binding, emergency disable and self-update behavior are unchanged.

### Regression coverage

The production line retains:

- pure policy coverage for five lease-busy retries and the sixth known-worker pause;
- pure policy coverage for the sixth unexplained lease-busy defensive global drain;
- mixed sequence coverage proving `5 × LEASE_BUSY -> DEFERRED -> LEASE_BUSY` leaves a lease-busy streak of one rather than seven;
- control-repository identity-change/reset coverage;
- real temporary-Git integration coverage that keeps the control task alive, crosses the six-consecutive-busy threshold, queues a second repository afterwards and requires that second task to start before the control task is released;
- explicit integration evidence that the known-worker path uses the control-repository pause rather than the global-drain path;
- full parallel/resource/repository lease regression coverage;
- macOS smoke coverage for the policy and real overlap regression;
- current-documentation and release-metadata drift checks.

### Closure evidence

- `docs/CHANGELOG.md` records BUG-002 as fixed under v4.18.14 behavior.
- Later released source retained those semantics; v4.18.15 explicitly states that it preserved the 4.18.14 BUG-002 admission behavior.
- Current production documentation and tests describe the repaired policy as established behavior rather than pending candidate work.
- The historical `v4.18.14` tag is absent from the remote tag set. Do not fabricate or back-date that tag merely to satisfy old prose; the durable source/release lineage above is the closure record.
- `v4.18.13` remains the explicit pre-fix rollback baseline for historical comparison.

---

## New bug template

```text
## BUG-NNN — short title

Status: Open
Priority: P0/P1/P2/P3
First confirmed: YYYY-MM-DD
Area: ...

### Symptom
...

### Evidence / reproduction
...

### Impact
...

### Planned repair
...

### Required regression coverage
...

### Closure criteria
...
```
