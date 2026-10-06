# Host Ops absorption — completed

Status: **completed on 2026-10-06**.

Local Agent is the sole brain/orchestrator. The maintained deterministic host/remote capability layer is `local_agent.host_ops`; the standalone `MichalMatu/host-ops` repository is a frozen donor/research archive, not a canonical execution target.

## Final architecture

```text
ChatGPT / planner
    -> Local Agent
        repository identity
        canonical admission
        scheduling and resource arbitration
        watchdogs and process lifecycle
        durable task/run/result evidence
        -> local_agent.host_ops
            deterministic validation
            bounded machine/remote-host effects
            structured evidence
            -> OS / Git / browser / ADB / serial / storage / SSH / remote host
```

The absorbed subsystem must never own repository routing, task planning, orchestration retries, agent bindings, Conversation Fabric policy or a second daemon lifecycle.

## Source absorption

PR #176 imported donor `host-ops@b12b6f33a5ee667201d4bddcbfa3cb1d1cb2948b` under `local_agent.host_ops` and preserved:

- `core -> capabilities -> workflows -> cli` dependency direction;
- JSON contract version 1;
- the full donor pytest regression suite under `host_ops_tests/`;
- architecture/design gates;
- a dedicated Host Ops coverage floor of at least 85%;
- reusable architecture, security and operations documentation under `docs/host_ops/`.

PR #176 merged at `4c0ea4c975e772ce7da776b8fe1f6508cf690c7f`; post-merge CI #2318 passed all six gates.

## Live Mac cutover evidence

The installed daemon self-updated to `a41689175f176535039216a3879295d10942962e` before provisioning.

The supported repository-admin path then provisioned the `local-agent` self-target:

- machine registry identity: `local-agent -> MichalMatu/local-agent`;
- canonical binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`;
- remote `local-agent/agent-control` created;
- hard binding committed on that control branch;
- independent control/work/checkpoint workspaces validated;
- catalog/registry/control binding equality validated;
- absorbed CLI smoke returned JSON contract `1` and a bounded macOS host profile.

After supervisor reload, fresh status from the active runtime showed `local-agent` under the same supervisor as the other maintained machine targets, while standalone `host-ops` retained only stale pre-cutover status. A repo-scoped `status` request on `local-agent/agent-control` completed successfully with the exact self-target binding, proving the new control plane is live.

The current source therefore removes the standalone `host-ops` record from both `config/agent_bindings.json` and the Chat Bridge runtime example.

## Donor retention

Do not delete research history accidentally. The donor branch `work/cpu-gpu-routing` remains intentionally preserved until its experiment is explicitly closed or migrated.

Historical release notes may still describe the former standalone binding. Current operational documentation must not instruct new work to target it.

## Final execution rule

- host-maintenance -> target `local-agent`;
- generic host/remote capability implementation -> `local_agent.host_ops`;
- project edit/build/test -> the actual project target;
- donor `MichalMatu/host-ops` -> reference/research only, no new executable tasks.

## Exit criteria

All absorption criteria are satisfied when this retirement cutover is on `main` with green exact-head CI:

- one maintained orchestration authority: Local Agent;
- host-operation code/tests/docs maintained inside Local Agent;
- no standalone Host Ops canonical binding/runtime identity;
- self-target hard binding and live control-plane acceptance proven;
- donor research history preserved.
