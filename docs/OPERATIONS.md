# Local Agent Operations

This is the canonical operational workflow for `MichalMatu/local-agent`.

## Production topology

The production/runtime source is `~/local-agent` on `main`. Releases are tagged `vX.Y.Z`. Temporary `v*-staging` branches and detached worktrees are used only for candidate development and exact-SHA validation.

The recommended v4.11 multi-repository supervisor is:

```bash
python agent_parallel.py --registry "$HOME/Library/Application Support/local-agent/repositories.json" --max-workers 2
```

`agent_multirepo.py` remains the direct serial fallback with global concurrency one. Both entry points use the same daemon lock and the same repository registry/state layout.

## Control data

Each registered repository uses its own `agent-control` branch:

```text
.agent/tasks/<task-id>.json
.agent/runs/<task-id>.json
.agent/results/<task-id>.json
.agent/status/daemon.json
```

Task IDs/payloads are immutable within a repository. Interrupted claimed work is never silently replayed. Terminal results are durably spooled before publication; publication recovery may republish but may not re-execute commands.

## Parallel resource contract

Unknown work is safe by default.

If `resources` is absent, malformed or oversized, the effective resource is full-machine exclusivity:

```json
{"resources": ["machine"]}
```

Clearly software-only work may opt into overlap:

```json
{"resources": [], "memory_limit_mb": 512}
```

Rules:

- non-machine admission requires an enabled `memory_limit_mb <= 1024`;
- otherwise the task falls back to `machine` exclusivity;
- named resources such as `platformio`, `usb` or `serial` are exclusive among tasks declaring the same name;
- a task containing `machine` is fully exclusive;
- resource declarations are planner contracts, not command inspection;
- hardware/USB/serial/flashing/unknown heavy work should remain machine-exclusive unless an explicit safe resource model exists;
- machine and named resource lock descriptors are inherited into descendants and remain held until the last descendant exits.

One repository still executes only one claimed task at a time. Different repositories may overlap only when their effective resources permit it.

## Development workflow

1. Read `AGENTS.md` and the target repository's planner instructions.
2. Inspect current source plus `.agent/status/daemon.json` and relevant run/result evidence.
3. Confirm the intended `work_branch` explicitly when it is not the repository default.
4. Prepare the smallest deterministic change.
5. Classify resources conservatively before queueing the task.
6. Queue a new unique task through that repository's `agent-control` branch.
7. Follow the same digest/attempt until terminal evidence is published.
8. Diagnose real output; do not infer success from task submission.
9. Run focused verification first, then the broad final gate when warranted.
10. Publish validated source according to the target repository's Git policy.
11. Treat source publication and hardware flashing/runtime verification as separate gates.

For substantial staged coding work, prefer `workflow_policy: "efficient-verification-v1"`: `work` stages for implementation, `focused` stages for affected verification, and exactly one final `full` verification stage.

An autonomous Chat Bridge conversation should follow one active task at a time for its current goal. This planner-level sequencing does not reduce the production executor to global concurrency one: unrelated repositories or conversations may still overlap when their effective resources permit it. Always decide from the target repository's current status/run/result evidence.

## Multi-repository administration

Registry:

```text
~/Library/Application Support/local-agent/repositories.json
```

Commands:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
python agent_repo_admin.py provision --repository-id <id>
```

Provisioning is explicit and never a poll-loop side effect. Repository ids/remotes and normalized control/work/checkpoint paths must be disjoint.

Do not remove or identity-mutate an active registry entry while workers/descendants may still be alive.

## Control and maintenance

Repository workers may handle repository-local status/control but never supervisor-wide restart/self-update directly.

While workers are active, the parallel supervisor only performs a lightweight control probe. A real global control request stops new admission, lets current workers drain, then acquires all configured repository execution identities before handling the request.

Ordinary self-update maintenance waits for a natural idle window. Production self-update expects the installed source checkout to be a clean `main`; this is why production must run from `~/local-agent` on `main`, not from a detached staging worktree.

## Runtime bounds

Canonical defaults:

- command timeout 900 s, max 7200 s;
- no-output timeout 300 s, max 3600 s;
- whole-task budget 1800 s, max 21600 s;
- finalization reserve 60 s;
- normal RSS limit 4096 MiB, configurable max 16384 MiB;
- parallel-admission RSS ceiling 1024 MiB.

Command stdout capture is bounded. Runtime limits are loaded at daemon startup.

## Deployment

The recommended macOS template is:

```text
deploy/macos/com.michal.local-agent.parallel.plist
```

It runs `~/local-agent/agent_parallel.py --max-workers 2` and uses label `com.michal.local-agent`. Serial templates use the same label and are replacements, never additional services.

After a release:

1. ensure `~/local-agent` is clean and fast-forwarded to released `main`;
2. install/bootstrap the parallel plist;
3. verify `daemon_version`, `self_revision`, `execution_model` and `max_parallel_workers`;
4. queue a real bounded task;
5. keep the serial backup until the release has proven stable.

Rollback means stopping the parallel service, restoring the serial plist and starting `agent_multirepo.py`; repository workspaces/control branches do not require migration.

## Release flow

For non-trivial runtime changes:

1. create/use an isolated `v*-staging` branch/worktree based on current `main`;
2. implement and run focused verification there;
3. require compile, Ruff, full unittest/integration and macOS smoke on the exact candidate SHA;
4. review `main...candidate` and ensure no unrelated or fallback-breaking changes;
5. audit planner-facing Local Agent docs in every registered downstream repository and update any materially stale instructions;
6. fast-forward `main` to the validated candidate;
7. tag the released main commit `vX.Y.Z` matching `agent_version.RELEASE_VERSION`;
8. switch production back to `~/local-agent` on `main` and verify live status/result evidence;
9. remove obsolete staging worktrees/branches after the release is established.

## Downstream documentation gate

Current registered targets are LiteGraph, Growbox ML Controller and MatrixHub. Changes to task schema, resources, concurrency, status/control fields, execution model, deployment/self-update or planner flow require a downstream docs audit before release. See `AGENTS.md` for the exact files/branches that must be checked.

## Source of truth

1. real Local Agent command/result output;
2. target repository source/tests;
3. remote run/result/status evidence;
4. planner analysis.
