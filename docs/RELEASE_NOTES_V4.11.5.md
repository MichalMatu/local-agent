# local-agent v4.11.5

v4.11.5 is a focused control-plane hardening patch for the v4.11 bounded-parallel release line.

## Changes

- validates global daemon control ids with the same restricted identifier syntax used by repository-local control handling;
- keeps daemon control ACK paths strictly inside `.agent/daemon/acks/` after path normalization;
- prevents a transient `DEFERRED` global-control probe from starving unrelated repository task admission after the supervisor has completed its initial control service;
- preserves the existing drain behavior for confirmed `PENDING` global control requests;
- adds unit regressions for invalid/traversal control ids and a real temporary-Git integration test proving that an unrelated late software task can start while the designated control repository is busy;
- includes the new control hardening regression suite in macOS smoke CI;
- aligns downstream status documentation so repository-worker snapshots are not required to repeat supervisor-wide `max_parallel_workers`.

The patch does not change task schema, resource classification, machine/named-resource locking, claim/replay semantics, result durability, worker caps or the serial fallback.
