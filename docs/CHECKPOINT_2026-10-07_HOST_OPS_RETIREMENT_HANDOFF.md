# Checkpoint — Host Ops retirement handoff

Date: 2026-10-07

## Status

Host Ops absorption, final donor machine-target retirement, and donor repository archival are complete. **No standalone `host-ops` runtime or repository-lifecycle cleanup remains.**

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

`MichalMatu/host-ops` is archived/history-only:

- `main@fb55448752a36f3dbf12d14e07b4884956d3201b`;
- maintained runtime ownership is in `local-agent`;
- preserve `work/cpu-gpu-routing`;
- do not add new runtime/product behavior to the donor;
- `agent-control` remains historical/compatibility evidence only; the repository is archived and cannot resume maintained runtime ownership without an explicit future reversal.

## Terminal retirement evidence

The final cleanup completed on 2026-10-07:

- checkpoint `41e653110a4e8d6c88884ff58f34787c774cb0de` passed exact-head CI #2330 with no open PRs;
- fresh `local-agent/agent-control` showed `idle`, exact `self_revision=41e653110a4e8d6c88884ff58f34787c774cb0de`, and binding `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`;
- `local-agent-final-host-ops-retirement-preflight-20261007-v3` PASS:
  - JSON contract output exactly `1`;
  - bounded host-profile JSON valid;
  - donor registry record exact-bound to `16d688b6-b0ef-4905-a5bd-24e59c99cfb4` and disabled;
  - Local Agent binding exact;
  - no donor claims, unpublished result spool or dirty control checkout;
- preflight drafts v1/v2 were read-only audit-script failures caused by incorrect assumptions about the disabled registry/control checkout; neither performed a mutation, and v3 is the authoritative PASS;
- the donor `agent-control` queue had one historical task without a terminal result, `inspect-machine-resource-holder-20261006-v1`; it was not executed on the disabled target and was closed as `cancelled_by_operator`, while equivalent diagnostics already had a completed `local-agent` result; the donor queue then had zero pending tasks;
- `local-agent-remove-host-ops-machine-record-20261007-v1` PASS removed only `host-ops`; remaining registry order is `growclip, bloomml, matrixhub, tracker, shelly-link, photomap, ai-calls, hardware-lab, local-agent`;
- supported restart request `restart-after-host-ops-registry-retirement-20261007-v1` was accepted through canonical first-registry control `growclip`;
- `local-agent-post-host-ops-registry-removal-smoke-20261007-v1` PASS after restart:
  - JSON contract output exactly `1`;
  - bounded host-profile JSON valid;
  - registry contains no `host-ops`;
  - Local Agent binding remains `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`;
- fresh Local Agent status returned to `idle` on checkpoint source with the new post-restart worker;
- `host-ops/work/cpu-gpu-routing` remains preserved at `901c9c0844beadb8cbe545103b70ba23c7720f7e`;
- docs-only closeout `main@2a015feaba708cc40ddf28cd40b753d51f744280` passed exact-head CI #2331 and the live daemon self-updated to that source;
- archival draft `local-agent-archive-host-ops-donor-20261007-v1` failed in its first precheck because of a Python syntax error and performed no archival mutation;
- authoritative `local-agent-archive-host-ops-donor-20261007-v2` PASS verified donor `main@fb55448752a36f3dbf12d14e07b4884956d3201b`, zero open PRs and preserved `work/cpu-gpu-routing@901c9c0844beadb8cbe545103b70ba23c7720f7e`, then archived the repository and re-verified `archived=true` plus the preserved branch SHA.

## Exact next task

There is no remaining Host Ops retirement task. Do **not** re-run absorption, provisioning, disable, registry cleanup or donor archival. Future Host Ops work belongs in `local_agent.host_ops`; the archived donor is historical/research evidence only. Preserve `work/cpu-gpu-routing` and all research history; donor runtime ownership must never be restored.

## Safety boundaries

- Do not re-add `host-ops` to the source catalog.
- Do not reorder the machine registry.
- Do not change scheduler/max-worker semantics.
- Do not create a second planner, daemon or control plane.
- Do not delete donor research history.
- Do not infer live success from CI alone; require durable task/result evidence.
