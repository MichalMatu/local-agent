# Verification

## Canonical gate

There is one full repository verification entrypoint:

```bash
.venv/bin/python scripts/quality/verify.py
```

It is fail-fast and currently runs:

1. architecture contract checks;
2. design-budget checks;
3. Ruff lint/security rules;
4. Ruff formatting check;
5. strict mypy;
6. Bandit;
7. Bash syntax for the standalone backup utility;
8. `pip check`;
9. pytest with branch coverage, floor 85%, and a 60-second per-test timeout watchdog.

CI must call this entrypoint rather than duplicate the gate list. Selected high-risk validation
boundaries use bounded deterministic Hypothesis properties inside the normal pytest suite; these
properties are UNIT evidence and remain subject to the same 60-second watchdog.

## Fresh-checkout bootstrap

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pre-commit install
.venv/bin/python scripts/quality/verify.py
```

The `dev` extra pins the repository verification toolchain. Do not substitute unrelated global checker versions as acceptance evidence.

## Iteration policy

While changing code, run the narrowest check that can detect the current regression, for example:

```bash
.venv/bin/python -m pytest tests/unit/path/to/test_file.py -q
.venv/bin/python -m ruff check path/to/module.py path/to/test.py
.venv/bin/python scripts/quality/check_architecture.py
.venv/bin/python scripts/quality/check_design.py
```

Run the complete verifier after the coherent slice is ready. Completion command chains must fail fast; a later successful command must never hide an earlier failure.

Pre-commit is fast feedback only. It does not replace tests, coverage, Bandit, shell syntax or dependency verification.

## Supplemental CI checks

Routine push/pull-request CI also verifies that the root project builds, installs and starts from its wheel, and verifies the isolated `penplotter` and `cpu_gpu_benchmark` prototypes with their own pytest, Ruff formatting/lint and strict mypy configuration. These supplemental jobs do not extend production `host_ops` ownership or the canonical verifier scope.

Known-vulnerability auditing is deliberately separate from the canonical gate because advisory data and dependency resolution are network-backed and time-varying. `.github/workflows/dependency-audit.yml` runs `pip-audit==2.10.1` weekly and on manual dispatch against the root project and both isolated prototype project definitions. A dependency-audit failure is security maintenance evidence, not a reason to make the deterministic canonical verifier network-dependent.

## Gate policy

Quality gates are part of the repository contract. Do not lower coverage, raise global design limits, add broad ignores or remove security rules to make a change green.

When a gate is genuinely wrong:

1. demonstrate the false positive with a focused fixture/test;
2. make the smallest narrow exception or rule correction;
3. preserve the intended invariant;
4. keep regression evidence for the blocked and allowed cases.

Production-code design tripwires are currently: module 600 lines, class 300, function/method 150, 12 public methods per class and 8 explicit constructor parameters excluding `self`. They are upper bounds, not design targets.

New behavior needs meaningful success and failure tests even when aggregate coverage already exceeds 85%.

## Evidence levels

Evidence levels are not interchangeable:

- **UNIT** — isolated parsing, validation, command construction and policy.
- **CONTRACT** — architecture/design/schema invariants.
- **INTEGRATION** — real local implementation dependency in a controlled environment.
- **LIVE** — real external phone, SSH worker, network endpoint or removable medium.

Never report UNIT/CONTRACT evidence as proof of a physical target.

Routine CI must remain independent of private credentials, the user's phone, LAN devices and removable media.

## Regression workflow

For a reproducible defect:

1. reproduce the narrow failure;
2. fix the root cause;
3. keep the regression test;
4. run focused checks;
5. run the canonical verifier;
6. add LIVE evidence only when the claim depends on an external target.

Do not weaken an invariant merely because its test fails.

## External capability checkpoint

Before first live use of a new external capability, the candidate source should have:

- explicit owner/boundary/failure semantics;
- focused positive and negative tests;
- clean architecture/design/security gates;
- canonical verifier PASS on the exact candidate revision;
- final diff review for unrelated changes and stale docs;
- an explicit live smoke plan that starts with read-only identity/discovery and escalates effects deliberately.

If a live operation can partially commit before its final verification, the error/result must make that possibility clear and the operator must inspect the target before retrying blindly.

## Remote compute golden gate

Before treating SSH/local-Git/`remote_git` changes as ready for routine real-worker use, require:

1. canonical verifier PASS on the exact candidate;
2. no project-specific names leaking into generic runtime/docs/tests;
3. real-worker `run-current` from a clean repository with matching local/remote exact revision;
4. reuse of the same workspace after a previous command dirties tracked and nested-untracked Git state;
5. dirty local source rejected before SSH;
6. unreachable/unfetched exact revision rejected before readiness;
7. workspace repository binding cannot be silently changed;
8. worker-visible `--repo-url` override exercised independently of local origin transport;
9. project non-zero status preserved while readiness evidence remains true;
10. host/workspace lock contention returns the documented busy status;
11. timeout exercised on the real worker and lock reusable afterward;
12. final source/doc diff reviewed and reduced to the intended checkpoint.

The physical-worker portion is manual LIVE evidence, never routine CI.

## Golden checkpoint policy

A checkpoint is an immutable source identity, not a moving branch label:

1. review/squash the candidate over current `main`;
2. run the canonical verifier on that exact integrated commit;
3. perform the planned safe live smoke on that exact source;
4. optionally create an annotated golden tag only if it does not already exist;
5. never move an existing golden tag;
6. remove temporary work branches after successful integration/evidence capture.

If `main` changes during closeout, stop and re-audit rather than overwriting concurrent work.

## Output discipline

Verification output is bounded evidence. Do not copy secrets into logs or results; prefer field names, hashes, lengths, target identifiers and redacted previews.
