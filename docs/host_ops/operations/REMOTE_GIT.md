# Remote Git compute workflow

`python -m local_agent.host_ops remote git` is a project-agnostic workflow for reproducible remote compute. It prepares one exact Git commit on a configured SSH target and optionally executes caller-supplied argv from that checkout. It does not decide what to build or test.

## Normal path: current repository

From any clean Git checkout:

```bash
python -m local_agent.host_ops remote git run-current build-host \
  --lock build-slot \
  --timeout 3600 \
  -- make check
```

`run-current` derives the local repository root, selected remote (`origin` by default), exact `HEAD`, and a stable workspace key from the effective worker-visible repository URL. A dirty tracked or untracked worktree is rejected.

A clean worktree is necessary but not sufficient: the exact commit must also be reachable from branch or tag refs fetched by the worker. Clean but unpushed source therefore fails closed instead of accidentally using stale cached Git objects.

Useful overrides:

```bash
python -m local_agent.host_ops remote git run-current build-host \
  --repo-path /work/project \
  --remote upstream \
  --repo-url https://git.example.test/team/project.git \
  --workspace project-cache \
  -- make check
```

`--repo-url` changes only the worker-visible transport URL. It is useful when the local remote is a machine-local path, an SSH URL without worker credentials, or another endpoint the worker cannot reach. When `--workspace` is omitted, the effective worker-visible URL determines the default remote cache identity.

`prepare-current` performs the same source resolution and remote preparation without running a project command.

## Explicit lower-level path

Callers that already know source identity may use:

```bash
python -m local_agent.host_ops remote git prepare build-host \
  --repo https://git.example.test/team/project.git \
  --revision <FULL_GIT_SHA> \
  --workspace project-cache

python -m local_agent.host_ops remote git run build-host \
  --repo https://git.example.test/team/project.git \
  --revision <FULL_GIT_SHA> \
  --workspace project-cache \
  -- make check
```

Symbolic branches or tags are not accepted as `--revision`; source identity is always one full lowercase 40- or 64-hex object id.

## Worker prerequisites

The target must already provide:

- Bash;
- Git;
- `flock` (`util-linux` on Termux/Linux);
- network and credential access to the selected repository URL;
- the project-specific toolchain needed by the requested command.

`host-ops` does not silently install compilers, package managers, project dependencies, submodules or Git LFS tooling.

## Remote workspace contract

Remote state lives under:

```text
${XDG_CACHE_HOME:-$HOME/.cache}/host-ops/remote-git/
```

The owned cache/workspace/repository directories, repository marker and lock paths must have the expected non-symlink types. Type/symlink conflicts fail closed, and lock files are opened non-truncating before `flock`.

For each run the worker:

1. acquires the optional host-wide lock and mandatory workspace lock;
2. verifies that an existing workspace is bound to the same worker-visible repository URL;
3. creates or reuses the dedicated checkout;
4. points `origin` at the requested worker-visible repository URL;
5. fetches and prunes remote branches and tags;
6. proves the requested commit was fetched and is reachable from fetched `origin` branch or tag refs;
7. hard-resets and cleans the old checkout before changing revision;
8. checks out the exact commit detached;
9. hard-resets and cleans again;
10. proves `git rev-parse HEAD` equals the requested revision;
11. emits the readiness marker and only then executes caller argv.

A workspace name is a cache identity, not a reusable alias for arbitrary repositories. Each workspace is bound to one exact worker-visible repository URL. Reusing an explicit workspace with a different URL fails with exit 73. Existing pre-binding workspaces are adopted only when their current `origin` already matches the requested URL.

A failed first clone removes the partial checkout. Pre-checkout cleanup prevents artifacts from a previous build from blocking a revision change. Double-force Git clean also removes untracked nested Git repositories that a single-force clean intentionally preserves.

## Cache inventory and explicit removal

Remote Git cache state can be inspected without preparing a new revision:

```bash
python -m local_agent.host_ops remote git cache list build-host --json
```

The list operation enumerates validated workspaces and attempts the same non-blocking workspace lock used by prepare/run. A locked workspace is reported as `busy` without reading unlocked repository state. Ready entries include the bound repository URL and exact current HEAD; legacy/unbound and empty states remain explicit. Malformed paths, repository markers or Git evidence fail closed.

One cache workspace can be removed explicitly:

```bash
python -m local_agent.host_ops remote git cache remove build-host project-cache --json
```

Removal validates the workspace name, acquires the same workspace lock, rejects symlink/path conflicts, removes only that workspace directory and leaves the lock file itself in place. Lock contention returns exit 75. There is deliberately no age-based or heuristic auto-prune.

## Clean modes

Default `--clean worktree` preserves ignored dependency/build caches while removing non-ignored untracked state. `--clean full` removes ignored state too for a colder build.

Both modes discard tracked modifications produced by a previous remote command before the next revision is prepared.

## Locks and scheduling

Every workspace has a non-blocking kernel lock. `--lock NAME` adds a host-wide kernel lock, useful for constrained workers shared by several repositories. Lock contention returns exit 75.

When Local Agent owns dispatch, also use a named scheduler resource such as `host:termux-s22` when cross-repository queueing matters. The Local Agent resource queues admission; the remote kernel lock protects the worker from callers outside that scheduler as well.

## Command lifecycle

Caller argv is passed as positional data; `host-ops` does not concatenate it into bootstrap shell source. The command runs from the verified repository root.

Commands should remain in the foreground until their work is complete. Daemonizing or intentionally backgrounding descendants weakens timeout and lock-lifecycle guarantees and is outside this workflow contract.

Examples:

```bash
python -m local_agent.host_ops remote git run-current build-host -- npm test
python -m local_agent.host_ops remote git run-current build-host -- python3 -m pytest
python -m local_agent.host_ops remote git run-current build-host -- cargo test
python -m local_agent.host_ops remote git run-current build-host -- pio run
python -m local_agent.host_ops remote git run-current build-host -- cmake --build build
```

`host-ops` does not classify these as builds or tests. It only prepares exact source, runs explicit argv and returns bounded evidence.

## Repository URLs and secrets

HTTP(S) URLs with embedded user/password data, query strings or fragments are rejected because those forms are common secret-leak channels. `ssh://user@host/path` and scp-style SSH URLs remain valid; credentials stay in external SSH/Git configuration on the worker.

Do not put tokens, passwords, signed URLs or other secrets in task payloads, repository URLs, logs or structured results.

## Results and failure behavior

The readiness marker is emitted only after remote provenance and exact `HEAD` checks pass. JSON output includes source revision, effective repository URL, workspace, readiness, process state, duration and bounded stdout/stderr. `run-current` additionally records non-sensitive local repository context (root, selected remote name and exact revision).

Transport/setup failures, dirty local state, source-not-reachable failures, workspace/repository identity conflicts, lock contention and project-command failures remain distinct. Project exit codes are propagated. Local SSH execution remains bounded by normal host-ops `ExecutionLimits` timeout/output controls.

Relevant workflow exit codes include:

- `73`: remote workspace identity/path conflict;
- `74`: requested revision was not fetched/reachable or final exact-HEAD verification failed;
- `75`: host/workspace lock contention;
- `124`: local bounded SSH workflow timeout.

## Known intentional limits

- dirty or uncommitted source is not transferred; snapshot transfer is a separate future capability;
- submodule, LFS and dependency setup remains project/toolchain responsibility;
- the workflow is not a scheduler or build-system detector;
- the project command runs with the configured remote user's permissions and is not sandboxed.
