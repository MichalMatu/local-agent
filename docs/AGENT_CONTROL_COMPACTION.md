# agent-control history compaction

`agent-control` is runtime state, not project source history. Local Agent already bounds the current task/result/run/ACK files and uses shallow control checkouts, but ordinary Git commits still leave old runtime state reachable on the remote branch. Over time that remote history can become much larger than the current `.agent/` tree.

This maintenance path rewrites only `agent-control`. Project branches such as `main`, `develop` and work branches are not changed.

## Safety model

The compactor is fail-closed:

- dry-run is the default and does not rewrite history;
- apply mode must acquire the Local Agent daemon lock, so a running daemon blocks destructive maintenance;
- apply mode requires a verified full-history Git bundle of the target `agent-control` branch before any rewrite;
- the compacted root commit reuses the exact current Git tree object and verifies the tree SHA before publication;
- publication uses an exact `--force-with-lease=refs/heads/<branch>:<old-sha>` lease;
- if the remote branch changes while backup or compaction is in progress, the operation aborts rather than overwriting the new commit;
- after publication, the local control checkout is refreshed and reset to the rewritten remote branch.

The default compaction threshold is the same as `CONTROL_HISTORY_DEPTH` (currently 256 locally visible commits).

## Dry-run

Inspect every registered repository:

```bash
python -m local_agent.repository.compaction --all
```

Inspect one repository:

```bash
python -m local_agent.repository.compaction --repository-id growclip
```

The command prints one JSON record per repository. `plan.eligible=true` means the checkout is clean, is on its configured control branch, matches the remote HEAD and has reached the compaction threshold.

No branch is rewritten in dry-run mode.

## Apply

Stop Local Agent first. Apply mode also acquires the daemon lock and fails if another daemon/supervisor owns it.

Use a persistent backup directory outside project worktrees:

```bash
python -m local_agent.repository.compaction \
  --all \
  --apply \
  --backup-dir "$HOME/local-agent-backups/agent-control"
```

For one repository:

```bash
python -m local_agent.repository.compaction \
  --repository-id growclip \
  --apply \
  --backup-dir "$HOME/local-agent-backups/agent-control"
```

For an explicit one-time maintenance case where a control checkout has fewer than the normal threshold but still must be compacted, lower the threshold deliberately:

```bash
python -m local_agent.repository.compaction \
  --repository-id growclip \
  --threshold 1 \
  --apply \
  --backup-dir "$HOME/local-agent-backups/agent-control"
```

Do not use a lower threshold for routine maintenance.

## Backup contract

Before rewriting an eligible branch, the command performs a non-shallow, single-branch bare clone of `agent-control`, verifies that its HEAD still equals the planned remote SHA, creates a Git bundle containing the full reachable history of that branch, and runs `git bundle verify`.

The backup filename includes the repository id, UTC timestamp and original branch SHA. Keep these bundles until the migrated repositories have completed normal task/result cycles after the rewrite.

A bundle can be inspected without touching the remote repository:

```bash
git bundle list-heads /path/to/project-agent-control-*.bundle
```

Rollback should be an explicit operator action using the recorded old and current remote SHAs. Do not replace the exact lease with an unconditional `git push --force`.

## Post-migration verification

For each migrated repository verify:

1. the current `.agent/` tree is unchanged;
2. the local control checkout and remote `agent-control` resolve to the same new root commit;
3. a new task can be published;
4. Local Agent claims and executes it normally;
5. the result is published and visible on `agent-control`;
6. project source branches are unchanged.

Only after live task/result verification should old backup bundles be considered removable.
