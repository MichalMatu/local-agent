# Local Agent v4.19.11 checkpoint audit

Date: 2026-09-30

## Purpose

This checkpoint is a pre-development freeze after the Chat Bridge scheduling/control migration from assistant DOM markers to GitHub `conversation_controls`. The goal is to stabilize the current behavior, repair regressions introduced by the migration, strengthen the release gate and record remaining risks before new feature work resumes.

The deployed production baseline remains Local Agent v4.19.10 / Chat Bridge 0.6.1 until the explicit release decision advances `main`. The checkpoint source candidate is Local Agent v4.19.11 / Chat Bridge 0.6.2.

## Audit scope

Reviewed boundaries include:

- GitHub desired-state reconciliation, generation/idempotence and terminal safety state;
- browser delivery, exact conversation/tab authorization, manual `Run now` and assistant-error recovery;
- repository/task hard binding and planner scope;
- task schema, branch/path validation, patch/write/delete boundaries and payload transport;
- registered process spawning, process groups, shutdown races and output bounds;
- repository and machine/named-resource `flock` inheritance/recovery;
- guarded entrypoint, self-update/rollback and operator disable/control paths;
- scheduler/control admission ownership and parallel isolation;
- control Git publication/compaction safety;
- MCP policy and runtime dependency installation;
- CI, coverage, macOS smoke, browser smoke, release metadata and branch/release hygiene.

## P1 regression found and repaired

GitHub drift reconciliation could undo a deliberate local terminal stop. After an already-applied remote generation, `conversation_exhausted` or `assistant_retry_exhausted` advances local generation and disables the conversation. The previous reconcile path could classify that local generation change as ordinary drift and restore `enabled=true` from remote desired state.

The 4.19.11 repair defines the safety ownership boundary explicitly:

- `conversation_exhausted` remains terminal for the same hard binding, including when later GitHub pacing generations are still enabled;
- `assistant_retry_exhausted` remains terminal against the already-applied generation, while a strictly newer GitHub generation is treated as an explicit recovery decision;
- preserved terminal state clears conversation alarms and updates the applied-control journal so reconciliation cannot loop;
- manual `Run now` cannot bypass confirmed conversation exhaustion.

Dedicated regression coverage exercises same/new generation behavior, alarm state, applied-journal state and manual delivery.

## Historical BUG-001 closure revalidated

The backlog still described the September orphaned resource-lock incident as open even though guarded repository-lease recovery shipped in v4.18.5.

The current process model establishes why that repair covers the historical failure:

1. every task command descendant inherits its repository execution lease;
2. parallel resource admission additionally inherits the shared/exclusive `machine` flock and any named-resource flocks;
3. therefore a descendant that survives its worker while retaining a resource lock also retains an identifying repository lease;
4. guarded recovery discovers actual kernel lock holders rather than executable names, terminates only proven holders with bounded TERM -> KILL, then verifies lease release before execution resumes.

The checkpoint adds an explicit integration regression in `tests/test_lease_recovery.py` where a child inherits both repository and separate resource locks, the parent closes its copies, recovery identifies/kills the child through the repository lease, and both locks must then be reacquirable. The same module is part of macOS smoke.

This closes the documentation/test gap for the original BUG-001 incident. A future reproducer that retains only a resource lock while no identifying repository lease remains would be a distinct defect and should receive a new bug id.

## Release gate hardening

The checkpoint also:

- turns coverage reporting into a real gate with `--fail-under=70`;
- pins GitHub Actions dependencies to immutable commit SHAs;
- synchronizes Local Agent 4.19.11 / Chat Bridge 0.6.2 release metadata while keeping runtime schema 3, content protocol v13 and assistant guard v8 unchanged;
- preserves source-candidate vs deployed-production wording so a candidate cannot be presented as production before explicit release;
- retains full Linux tests/lint/compile, Python 3.14, real Chromium extension smoke and macOS smoke as independent CI jobs.

The exact checkpoint runtime/resource-regression SHA `5103272ed9e44f46abc4eec12d9947d4404b8137` passed all five canonical CI jobs, including macOS smoke. A final documentation-only SHA must pass the same matrix before merge.

## Broader code audit conclusions

No additional open P0/P1 runtime defect was identified in the reviewed boundaries.

Notable strong invariants confirmed by source and tests:

- task `agent_binding` is mandatory and exact before execution;
- `resources` is explicit, bounded and canonical; `machine` cannot be combined with named resources;
- `work_branch` is validated with both a bounded local grammar and `git check-ref-format --branch` before Git use;
- task payload-file references are task-directory scoped and reject traversal/symlink escape;
- workspace writes/deletes resolve against the workspace root and reject escape/root targets;
- patches use `git apply --check` before apply;
- dirty workspaces are checkpointed before destructive reset/clean;
- spawned commands go through the registered process lifecycle and inherit execution/resource lease descriptors deliberately;
- task stdout/result transport, command timeouts, idle timeouts, whole-task admission and RSS are bounded;
- interrupted claimed work is not automatically replayed;
- publication stages exact paths rather than broad `git add -A`;
- control-history rewrite uses exact `--force-with-lease`, not unconditional force;
- self-update installs the inspected revision, validates before restart and rolls back validation failure;
- MCP execution remains loopback-only and policy/risk-class gated;
- operator-mutating Bridge messages require the exact extension popup origin, while content-origin messages are revalidated against top-frame/tab/conversation identity.

Static review also found no production use of `os.system`, Python `eval`, `pickle`, broad `git add -A`, TODO/FIXME markers or an actual committed GitHub token. Shell execution remains centralized and intentional because shell command strings are the authorized task payload.

## Residual non-blocking risks / next hardening work

### P2 — Python runtime transitive dependencies are not reproducibly locked

`requirements-runtime.txt` pins `mcp==2.2.0`, but clean installs still resolve its transitive dependencies from broad version ranges. CI evidence shows packages such as `pydantic`, `cryptography`, `starlette`, `uvicorn`, `jsonschema` and others are selected at install time. Two fresh installations of the same Local Agent tag can therefore receive different runtime stacks.

This is release-engineering debt, not evidence of a current runtime failure. Do not add a last-minute ad-hoc freeze to 4.19.11: design one cross-platform constraints/lock workflow, validate it on Python 3.12/3.14 and macOS, and define how production dependency updates are applied independently from source self-update.

### P2 — `main` has no enforced branch protection / required checks

The repository reports `main` without enforced required status checks. The code-side release policy requires exact-candidate CI before advancing production, but GitHub currently does not enforce that invariant server-side.

After this checkpoint, configure branch protection/rulesets so `main` requires the canonical CI jobs and deliberate merge flow. This is repository administration, not a source-code fix.

### P2 — multi-profile Chat Bridge execution remains unsupported

Applied generations, alarms and in-flight delivery ownership are Chrome-profile local. Two profiles configured as active executors for the same conversation can both submit the same wake. The supported production topology remains one active production Chrome profile per managed conversation; additional profiles are diagnostic only. Supporting active multi-profile execution requires a real shared lease/owner protocol, not another local boolean.

### P3 — dependency/coverage follow-up

Overall Python coverage is currently just above the new 70% floor. High-risk execution primitives are well covered, but top-level orchestration still has weaker line coverage. Add scenario-focused orchestration/recovery tests first, then raise the global threshold incrementally (for example toward 75%) rather than using a cosmetic threshold bump.

### P3 — Bridge compatibility surface

Legacy DOM/LAB migration compatibility remains larger than the current GitHub authority surface. Do not add new scheduling heuristics there. Once the GitHub control plane has aged in production, remove obsolete pacing-only compatibility code/tests in a dedicated behavior-preserving cleanup.

## Release decision

The automated candidate gate can be considered closed only when the final documentation SHA is green across the complete CI matrix.

The **production release gate is not yet closed** by automated CI alone. Because 4.19.11 changes Chat Bridge control behavior, the repository's Golden Standard still requires one bounded production-shaped live Chrome validation using the exact candidate build and GitHub desired-state path, ending with the managed conversation PAUSED. Only after that proof should `main` advance and tag `v4.19.11`.

No registered downstream planner task/schema/control transport changed in 4.19.11; the checkpoint therefore requires no downstream migration beyond confirming existing GitHub-managed scheduling guidance remains compatible.
