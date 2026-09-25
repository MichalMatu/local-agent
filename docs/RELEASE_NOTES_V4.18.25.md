# Local Agent 4.18.25

## Summary

Local Agent now keeps repository `agent-control` history bounded instead of allowing ordinary runtime status/task/result cleanup commits to accumulate indefinitely on the remote branch.

The change affects only the Local Agent control plane. Project source branches, task schema, repository binding, resource scheduling, executor behavior, Chat Bridge protocol and planner contract are unchanged.

## Automatic control-history compaction

- `agent-control` still retains the current bounded runtime state (`tasks`, `results`, `runs`, daemon ACKs and status) using the existing retention policy.
- When a real control checkout reaches the existing `CONTROL_HISTORY_DEPTH` boundary (256 locally visible commits), runtime cleanup may replace the remote control history with one new root commit that reuses the exact current Git tree.
- The tree SHA is verified before publication, so compaction changes history ancestry rather than the current `.agent/` contents.
- Publication uses an exact `--force-with-lease` against the previously observed remote SHA. Compaction never falls back to unconditional `git push --force`.
- A competing remote update on the old history line causes compaction to fail closed without overwriting it.
- If the compacting push was accepted but the network response was lost, Local Agent reconciles against the remote ref instead of blindly retrying the force push.
- If a fresh task/status commit lands immediately after the new compacted root, Local Agent recognizes the remote as a descendant of that root and realigns the local control checkout to the newer tip, preserving the new state.
- Compaction failure is maintenance-degraded rather than task-fatal: ordinary runtime work continues and a later cleanup cycle can retry safely.

## One-time migration tooling

A new administrative command supports the existing repositories that already have oversized `agent-control` histories:

```bash
python -m local_agent.repository.compaction --all
```

Dry-run is the default. Apply mode requires both a stopped Local Agent daemon (enforced through the daemon lock) and an explicit persistent backup directory:

```bash
python -m local_agent.repository.compaction \
  --all \
  --apply \
  --backup-dir "$HOME/local-agent-backups/agent-control"
```

Before each eligible rewrite, apply mode creates a non-shallow branch-only backup of the complete reachable `agent-control` history, writes it as a Git bundle, verifies the bundle, rechecks the expected remote SHA and only then performs the exact-lease rewrite.

See `AGENT_CONTROL_COMPACTION.md` for the operational procedure and post-migration checks.

## Verification

Regression coverage uses real temporary Git repositories for the control-history behavior, including:

- dry-run non-mutation;
- exact-tree root compaction;
- verified full-history bundle backup;
- a competing pre-push remote commit;
- an accepted force push with a simulated lost client response;
- an accepted force push followed immediately by a new remote control commit;
- runtime-GC integration when no artifact deletion is otherwise required.

The normal release matrix also covers compile/lint, unit and integration tests, coverage, Python 3.14 compatibility, macOS smoke and real browser smoke.

## Planner and downstream compatibility

No downstream planner migration is required. Task JSON, `work_branch`, repository binding, resource declarations, result schema and Chat Bridge control protocol are unchanged. This release changes only storage/history maintenance for the Git-backed Local Agent control plane.
