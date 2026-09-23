# Test Execution Golden Plan

Status: staging design for v4.11.6.

## Goal

Make Local Agent verification deterministic, fast enough for normal development, observable without log spam, and strict enough that one final full gate can still certify a release. The solution must reduce false negatives caused by machine contention without hiding real failures or inflating assertions/timeouts.

## Problems to solve

1. Full Vitest and Playwright runs can consume tens of minutes and have produced false timeout failures under parallel machine load.
2. Serializing every test removes those false failures but can turn normal verification into an hour-long gate.
3. Long test suites inside Git hooks hold Git operations open for too long and mix transport failures with test failures.
4. Successful test suites stream large amounts of fixture/output noise into the global Local Agent log.
5. Repeated worker/control failures retry too aggressively and repeat identical log lines.
6. The planner has an efficient-verification policy, but downstream repositories do not consistently map their test commands to work/focused/full stages.
7. Heavy commands can be started indirectly by npm/hooks, so task-level resource classification must cover the complete stage, not only the top-level executable.

## Golden verification model

### Tier 0: syntax/config smoke

Target: seconds, always cheap.

Examples: py_compile, Ruff on touched Python files, prettier check on touched JS/TS/Svelte files, schema/config validation.

### Tier 1: focused regression

Target: normally under 2-5 minutes.

Run only tests owned by the changed module plus the smallest directly dependent integration path. Re-run known flaky candidates at controlled worker counts when diagnosing concurrency.

### Tier 2: bounded full suite

Target: one broad software suite near the end of the task, not after every edit.

Use measured worker counts. Start conservative, benchmark 1 vs 2 workers, and choose the fastest configuration that passes repeatedly under realistic host load. Do not increase individual test timeouts merely to compensate for contention.

### Tier 3: golden/release flow

Run once per candidate SHA after focused evidence is green. Includes full unit/integration coverage, representative browser/e2e flow, scheduler/resource smoke, log-output checks, and macOS production-path smoke for Local Agent releases.

Soak/hardware tests remain separate and are required only when the changed subsystem needs them.

## Required Local Agent changes

### A. Stage output policy

Add a validated per-stage `output_policy` for structured `steps` / `verify_steps`:

- `stream` - current behavior, appropriate for interactive/short commands.
- `summary` - retain full bounded output in the task result while suppressing routine live lines; emit start, progress markers, periodic heartbeat, completion summary, and on failure a bounded tail.

No command-name heuristics. The planner must opt a stage into `summary` explicitly. Legacy commands remain `stream` for compatibility.

Result evidence must retain the same bounded raw output regardless of live policy.

### B. Failure-tail policy

For `summary` stages, on non-zero exit emit a bounded tail with an explicit truncation marker. Successful stages emit only exit code, elapsed time, and captured-output byte/character count.

Progress markers remain visible immediately and are never suppressed.

### C. Retry/backoff and duplicate-log suppression

- repeated repository-worker failures: exponential retry starting at 2 s, capped at 300 s;
- control-probe deferrals: short exponential retry starting at 2 s, capped at 15 s so control stays responsive;
- identical repeated supervisor failures: log at most once per 60 s while maintaining counters in state/telemetry;
- successful/normal worker outcomes reset the relevant failure fingerprint/counter.

### D. Heavy-stage resource policy

A full test/build/browser stage is machine-exclusive unless a repository has measured evidence for a narrower named resource. Parallel software tasks may continue only when they do not contend with a declared heavy stage.

The resource lease covers descendants and hooks. Do not rely on executable-name inspection.

### E. Git hook policy

Pre-commit/pre-push hooks must stay short. Full unit/e2e suites belong in explicit verification stages before `git push`; hooks may run formatting/static/quick contract checks.

### F. Exit-code evidence

Preserve direct subprocess return codes. A signal-style shell exit such as 141 is evidence, not automatically a Local Agent defect. When nested tooling prints a more specific failure, retain both shell exit and bounded output so the planner can distinguish test failure, transport failure and actual signal termination.

## Benchmark matrix

For LiteGraph, collect elapsed time, peak RSS, host load/memory and pass/fail for:

1. RF433 focused Vitest at 1 and 2 workers, repeated at least twice.
2. Previously flaky browser subset at Playwright workers 1 and 2.
3. Full Vitest at workers 1 and 2, one controlled run each unless an early failure makes the comparison unnecessary.
4. A representative routed Playwright smoke subset at workers 1 and 2.
5. Full Playwright only once on the selected candidate configuration.

Do not benchmark 4+ workers again unless 2-worker evidence is stable; previous evidence already showed contention at 4.

## Local Agent flow tests

The v4.11.6 candidate must demonstrate:

1. two independent `resources: []` software-only tasks can overlap;
2. a `resources: ["machine"]` task drains/blocks unrelated admission until complete;
3. a named-resource collision serializes only the matching tasks;
4. a deterministic worker failure backs off instead of looping every second;
5. repeated control-probe deferral stays responsive while rate-limiting logs;
6. `summary` output policy keeps successful noisy tests out of the global log while raw bounded evidence remains in result JSON;
7. a failing `summary` stage surfaces a useful bounded tail;
8. progress markers and heartbeat continue during quiet stages;
9. process descendants are cleaned and inherited leases remain held until descendants exit;
10. self-update/restart waits for a quiescent worker set.

## Performance acceptance criteria

- Normal focused verification should not invoke a repository-wide full suite unless the change is cross-cutting.
- Only one final full verification stage is allowed under `efficient-verification-v1`.
- No repeated identical supervisor error line more frequently than once per 60 s.
- No successful noisy test suite should flood the global log when using `output_policy: summary`.
- A quiet stage must still publish heartbeat/progress and remain subject to idle/command/RSS watchdogs.
- Selected LiteGraph worker counts must be based on measured repeated evidence, not on timeout inflation.

## Release gates

1. exact candidate SHA compiles;
2. Ruff is clean;
3. focused Local Agent unit tests pass;
4. full `python -m unittest discover -q` passes;
5. real temporary-Git scheduler/resource integration flows pass;
6. macOS smoke passes on the candidate;
7. LiteGraph benchmark task records selected Vitest/Playwright worker policy;
8. downstream planner docs are synchronized;
9. `main...candidate` contains no unrelated changes;
10. only then fast-forward `main`, bump/tag release, self-update production, and run one real queued post-release task.

## Documentation updates required during implementation

- `AGENTS.md`: output policy, log/backoff invariants, verification rules.
- `docs/OPERATIONS.md`: tiered verification and heavy-stage resource guidance.
- `docs/GOLDEN_STANDARD.md`: production invariants after validation.
- `docs/AUTONOMOUS_CHAT_LOOP.md`: planner construction of work/focused/full stages and output policy.
- `docs/MULTI_REPOSITORY.md`: scheduler failure/backoff behavior where relevant.
- release notes for v4.11.6.
- downstream Local Agent instructions in LiteGraph, Growbox, MatrixHub and ESP32-C6 when the planner/task contract changes.

## Non-goals

- Do not weaken assertions to make overloaded runs green.
- Do not globally increase 5 s/10 s test timeouts as the primary fix.
- Do not serialize all development tests forever.
- Do not hide failed command output.
- Do not make Local Agent infer test type from arbitrary shell command strings.

### Supervisor retry evidence
Focused verification covers worker 2-300 s retry, control-DEFERRED 2-15 s retry, 60 s log gating, reset, and the busy-control-repository late-task integration. Accelerate retry knobs in tests rather than increasing test deadlines.
