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
- if a competing remote update lands before the rewrite, the exact lease rejects the rewrite rather than overwriting that update;
- if the rewrite was accepted but the client loses the push response, the compactor inspects the remote instead of blindly retrying the force push;
- if a new task/status commit lands immediately after the compacted root, the compactor recognizes the newer remote as a descendant of that root and realigns the local checkout to the newer tip;
- project source branches are never targets of this maintenance path.

The administrative migration command defaults to the existing `CONTROL_HISTORY_DEPTH` boundary: 256 locally visible commits. This keeps ordinary dry-run output focused on repositories that have actually accumulated substantial control history.

## Migration gate and automatic runtime compaction

Automatic history rewriting is opt-in at the Git-history level. A managed control lineage contains the versioned commit trailer:

```text
Local-Agent-Control-History: bounded-v1
```

Fresh control branches created by this release contain the trailer in their initial root commit. The one-time administrative migration also writes the trailer into the new compacted root. Existing legacy `agent-control` branches do not contain it, so merely upgrading Local Agent cannot cause those old histories to be rewritten automatically before their verified backup migration.

After a branch is managed, ordinary runtime cleanup keeps its remote ancestry bounded. The runtime compaction threshold is half of the shallow control-history window: currently 128 commits with a 256-commit visible window. Policy detection scans the full 256-commit window. This leaves roughly 128 commits of scheduling/race margin after the automatic threshold is reached, rather than requiring Local Agent to hit one exact boundary before the marked root falls out of a shallow checkout.

Automatic compaction uses the same exact-tree and exact-lease rules as the administrative path. It does **not** create a full Git bundle every time the runtime threshold is reached; those recurring commits are ephemeral control-plane history. A compaction error is maintenance-degraded rather than task-fatal, so normal execution can continue and a later cleanup cycle can retry.

The verified bundle backup requirement below applies to the one-time migration of repositories that already accumulated large historical `agent-control` branches.

## Dry-run

Inspect every registered repository:

```bash
python -m local_agent.repository.compaction --all
```

Inspect one repository:

```bash
python -m local_agent.repository.compaction --repository-id growclip
```

The command prints one JSON record per repository. `plan.eligible=true` means the checkout is clean, is on its configured control branch, matches the remote HEAD and has reached the administrative compaction threshold.

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

For an explicit one-time maintenance case where a control checkout has fewer than the normal administrative threshold but still must be compacted, lower the threshold deliberately:

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
2. the local control checkout and remote `agent-control` resolve to the same rewritten lineage;
3. the new compacted root contains the `bounded-v1` history-policy trailer;
4. a new task can be published;
5. Local Agent claims and executes it normally;
6. the result is published and visible on `agent-control`;
7. a subsequent bounded pull still works from the existing shallow control checkout;
8. project source branches are unchanged.

Only after live task/result verification should old backup bundles be considered removable.
