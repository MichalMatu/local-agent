# Checkpoint — Host Ops retirement handoff

Date: 2026-10-07

## Status

Host Ops absorption is complete in source and live runtime. The remaining work is **final donor retirement cleanup**, not another integration stage.

Current source baseline before this checkpoint commit:

- `local-agent/main@1571ac6458d58243f00960aa9777cf46272524e0`;
- CI #2329: PASS;
- no open PRs;
- operational branches: `main`, `agent-control`, `chat-bridge-state`, `operator-control`;
- PR #176 absorbed Host Ops runtime into `local_agent.host_ops`;
- PR #177 removed the standalone `host-ops` execution identity from the canonical source catalog.

Current live Local Agent evidence:

- repository id: `local-agent`;
- binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`;
- `local-agent/agent-control` exists;
- daemon is healthy/idle and self-updated to `1571ac6458d58243f00960aa9777cf46272524e0` before this checkpoint commit;
- execution model remains `multi_repository_worker` / parallel;
- absorbed Host Ops JSON contract remains version `1`.

## Accepted live cutover evidence

The following durable `local-agent/agent-control` results are PASS:

1. `local-agent-absorbed-host-ops-smoke-20261006-v1`
   - `python -m local_agent.host_ops --json-contract-version` -> `1`;
   - `python -m local_agent.host_ops host profile --json` -> bounded Apple M1 host facts.

2. `disable-host-ops-machine-target-20261006-v1`
   - verified exact donor and Local Agent identities/bindings;
   - set the standalone `host-ops` machine-registry record to `enabled=false`;
   - repository-admin listing afterward contained `local-agent` and omitted disabled `host-ops`.

3. `local-agent-post-host-ops-disable-smoke-20261006-v1`
   - ran through target `local-agent` after donor disable;
   - JSON contract -> `1`;
   - host profile -> valid bounded Apple M1 JSON.

This proves that maintained host-maintenance execution no longer depends on the standalone donor target.

## Donor state

`MichalMatu/host-ops` is frozen/history-only:

- `main@fb55448752a36f3dbf12d14e07b4884956d3201b`;
- maintained runtime ownership is in `local-agent`;
- preserve `work/cpu-gpu-routing`;
- do not add new runtime/product behavior to the donor;
- `agent-control` remains historical/compatibility evidence until final machine-registry retirement is complete.

## Exact next task

Do **not** re-run the absorption or re-provision `local-agent`.

1. Read fresh `local-agent/main`, CI and `local-agent/agent-control` status.
2. Require the live daemon to self-update to this checkpoint commit or a later descendant and be idle/healthy.
3. Run one final bounded host-maintenance smoke through target `local-agent`:
   - `python -m local_agent.host_ops --json-contract-version` -> exactly `1`;
   - `python -m local_agent.host_ops host profile --json` -> valid bounded JSON.
4. Inspect the machine registry. The `host-ops` record should be disabled; `local-agent` must remain exact-bound.
5. With no pending/claimed donor work, remove only the disabled `host-ops` registry record. Preserve the order of every remaining record.
6. Restart through the supported supervisor/control path and verify:
   - healthy/idle Local Agent;
   - `local-agent` status still publishes on its own `agent-control`;
   - no binding/catalog errors;
   - no maintained workflow requires the donor checkout.
7. Run one final post-removal `local-agent` smoke.
8. Update this handoff/absorption plan with terminal evidence.
9. Only then decide whether to archive the donor repository. Preserve `work/cpu-gpu-routing` or export its research history first.

## Safety boundaries

- Do not re-add `host-ops` to the source catalog.
- Do not reorder the machine registry.
- Do not change scheduler/max-worker semantics.
- Do not create a second planner, daemon or control plane.
- Do not delete donor research history.
- Do not infer live success from CI alone; require durable task/result evidence.
