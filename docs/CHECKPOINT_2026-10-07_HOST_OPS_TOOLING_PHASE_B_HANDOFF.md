# Checkpoint — Host Ops Tooling Phase B handoff

Date: 2026-10-07

Status: **ready for fresh-chat continuation**.

Canonical source at handoff: `main@ca08bb848c5911aa6f7f87581c8c858b41888f11`.

Production daemon release line remains `v4.20.6`. The live Local Agent daemon and the parallel supervisor both report `self_revision=ca08bb848c5911aa6f7f87581c8c858b41888f11`. The designated supervisor-control repository is `growclip`. Both the repository worker view and supervisor view are idle at handoff. `local-agent/agent-control` has no pending tasks.

Exact-head GitHub Actions run `37558788662` for `ca08bb848c5911aa6f7f87581c8c858b41888f11` passed all canonical jobs:

- `absorbed-host-ops`;
- `test`;
- `coverage`;
- `bridge-browser`;
- `python-314`;
- `macos-smoke`.

## Active product direction

Host Ops has been absorbed into `local_agent.host_ops`; the standalone `MichalMatu/host-ops` repository remains archived/history-only and must not return to the source catalog or machine registry.

The active development sequence is intentionally frozen:

```text
inventory existing tools
  -> debug / test / harden every existing tool
  -> define Local Agent <-> Tool Runtime contract
  -> migrate existing tools onto that contract without semantic drift
  -> broaden Host Ops into a complete reusable multi-tool runtime
  -> later expose better ChatGPT-plugin ergonomics over the same GitHub control/evidence plane
```

Do not skip directly to a generic registry, new plugin framework or broad capability expansion.

The future product transport remains:

```text
ChatGPT / future plugin
  -> GitHub control + evidence
    -> Local Agent planning / admission / scheduling / policy
      -> Host Ops Tool Runtime
        -> machine / device / remote / browser effects
```

There is no target MCP server, no direct ChatGPT-to-Local-Agent execution transport and no second scheduler/control plane.

## Tool Runtime mental model

The consolidation goal is to turn Host Ops from a collection of unrelated CLI commands into one coherent deterministic toolbox.

A future internal tool definition should eventually describe at least:

- stable tool identity;
- validated input;
- structured result/error;
- effect/risk class;
- execution bounds;
- target identity;
- scheduler-resource requirements when genuinely shared;
- artifact behavior.

Important distinction discovered during real ADB work:

**tool target identity is not the same thing as scheduler resource identity.**

Project-dedicated hardware tasks currently remain `resources: []`. Device/endpoint discovery and exact-target validation happen inside the task immediately before use. Named resources are only for genuinely shared external conflicts across repositories; `machine` remains whole-host exclusivity.

## Conversation Fabric / Chat Bridge boundary

Conversation Fabric remains Local Agent orchestration. It owns:

- whether children are delegated;
- campaign identity/capacity/ownership;
- retry/retire policy;
- stable-result adoption;
- Result Vault policy;
- campaign completion;
- synthesis.

Deterministic browser/chat-UI lifecycle primitives may later share the Tool Runtime contract semantically, for example exact tab creation, prompt insertion/submission, route/ownership observation, result extraction and exact owned-tab close.

Do **not** physically move those extension-owned primitives into Python Host Ops by inventing a new browser RPC/control transport. The authenticated primary-Chrome production authority remains in Chat Bridge until an architecture-preserving migration exists.

A delegate request is not proof that children started. Parent waiting/collection begins only after explicit `conversation_fabric_started`. Rejection is terminal for that request and explicitly means no new delegation started.

The fix for this contract is in `3e5462881695ee54fd4aa6a6b201422b0326ef19`.

## Canonical inventory

The current inventory is:

`docs/host_ops/TOOL_INVENTORY.md`

It covers:

- core bounded process execution/config/diagnostics;
- ADB;
- host profile;
- executable inspection;
- network;
- serial;
- macOS USB/serial/storage;
- local artifacts/files;
- local Git support;
- SSH;
- remote-Git workflows;
- removable-media deployment;
- Host Ops browser operations;
- deterministic Chat Bridge primitives that are semantic Tool Runtime candidates.

The inventory is descriptive. It does not itself authorize broader behavior.

## Phase B completed slice — ADB

Existing ADB capability now has real Samsung Galaxy S22+ evidence for:

- wireless discovery;
- exact identity;
- bounded logcat;
- verified push;
- verified pull.

### ADB bugs found and fixed

1. Real Samsung identity exposed a multiline vendor property that made parsing a full `getprop` dump invalid.

   Fix: `f92feebd3b2dafe5e5de36f5e40d83ab25fa72ec` queries only the fixed identity properties under one shared operation budget.

2. First verified transfer reached remote SHA-256 verification but Android `/system/bin/sh` rejected the compound hash helper script.

   Fix: `a2808e0352d36c0d3958e12284712dee468a1a31` replaced that shell script with bounded fixed-command fallback:
   `sha256sum -> toybox sha256sum -> openssl dgst -sha256`.

3. A parallel test cleanup removed the old broad `test_adb_remote_files.py` suite. Relevant protocol coverage was intentionally consolidated rather than blindly restoring the obsolete suite.

   Consolidated coverage head: `cc234ddae3f44de21c1672b243684939531b35ce`.

### Wireless ADB identity finding

The same phone remained reachable while its observed transport changed from:

`192.168.0.100:34791`

to:

`192.168.0.100:38871`.

mDNS advertised the new `_adb-tls-connect._tcp` endpoint.

Therefore a wireless ADB `IP:port` is an ephemeral transport locator. Do not use it as durable device identity or as a scheduler lock identity.

### Final verified transfer evidence

Task:

`local-agent-host-ops-adb-transfer-e2e-20261007-v4`

Result: `done`.

It rediscovered one exact ready Samsung SM-S906B / product `g0sxeea`, then:

- pushed a disposable 33-byte file to `/data/local/tmp`;
- pulled it back through literal `/private/tmp` on macOS;
- verified identical SHA-256 on both directions;
- reported `local_directory_synced=true`;
- cleaned the disposable local and remote files;
- left Git worktrees unchanged.

Verified SHA-256:

`621a50e0895562e3d0bd28423d88921023b274332ccf171417af406494409545`.

The earlier V3 pull failure was not a capability bug: macOS `/tmp` is symlinked to `/private/tmp`, and the capability intentionally rejects a symlinked local destination directory. V4 used the literal real path and passed.

ADB expansion such as general wireless pair/connect/disconnect, broader shell/install/forward operations remains deferred until the existing-tool hardening phase is complete and the shared Tool Runtime contract is defined.

## Phase B current slice — SSH / Termux

SSH hardening has started.

Configured target:

`termux-phone`

Current documented endpoint:

`192.168.0.100:8022`

Expected remote user:

`u0_a520`.

Baseline task:

`local-agent-host-ops-ssh-check-e2e-20261007-v1`

Result: `done`.

Evidence:

- TCP probe to `192.168.0.100:8022` connected successfully;
- `ssh check termux-phone --timeout 10 --json` passed;
- strict host-key verification and configured public-key authentication passed;
- remote account reported `u0_a520`;
- `identity_matches=true`;
- no repository edits, timeout, truncation or background leak.

### Exact next work

Continue SSH/Termux hardening in this order:

1. bounded `ssh exec termux-phone` identity/environment smoke;
2. verified SSH push of one disposable small file;
3. verified SSH pull of that file/result;
4. cleanup only the exact disposable remote/local files;
5. inspect failures and harden only real defects;
6. record live evidence in `docs/host_ops/TOOL_INVENTORY.md`;
7. require exact-head full CI before declaring SSH existing surface complete.

Do not weaken strict host-key checking, batch public-key auth, explicit configured user/key or `-F /dev/null`.

`ssh exec` is general remote-code authority and must later be classified as arbitrary-code-like in the Tool Runtime effect taxonomy.

## Remaining Phase B queue after SSH

After SSH existing surface is proven, continue the current tools rather than expanding breadth:

1. physical serial-device transaction;
2. macOS removable storage inspect/mount/deploy/eject with disposable media when available;
3. browser/Chat Bridge deterministic primitives and lifecycle hardening;
4. whole-operation timeout normalization for multi-process workflows;
5. explicit size/time bounds for local artifact hash/copy;
6. JSON success/error consistency audit;
7. effect/risk classification and target/resource-identity review across all maintained tools.

Only after this queue is sufficiently closed should work begin on the shared Local Agent <-> Tool Runtime contract.

## Runtime / execution invariants

- Executable host-maintenance target: `local-agent`.
- Canonical binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`.
- Use direct GitHub edits for exact source/documentation diffs that CI can verify.
- Use Local Agent for Mac commands, local builds/tests, physical devices and host state.
- Conversation Fabric children are reasoning-only; they do not mutate repositories or run machine commands.
- Resolve actual execution target from the runtime catalog before every executable task.
- Repositories with `execution_enabled=false` may be inspected but must not receive executable tasks.
- Current project/dedicated-hardware task policy is `resources: []`; use named resources only for genuine shared conflicts and `machine` only for whole-host exclusivity.
- Global restart/self-update/status control belongs to the **first enabled machine-registry repository**, currently `growclip`; repository-scoped status/task evidence for Local Agent itself remains under `local-agent/agent-control`.
- Production supervisor: parallel multi-repository scheduler, max workers 4.
- Do not alter frozen scheduler/model/worker settings as part of tooling cleanup.

## Handoff start procedure

A fresh parent should:

1. read `AGENTS.md`;
2. read `docs/CURRENT_HANDOFF.md`;
3. read this checkpoint;
4. read `docs/DEVELOPMENT_PLAN.md`;
5. read `docs/host_ops/TOOL_INVENTORY.md`;
6. read `docs/MULTI_REPOSITORY.md`;
7. inspect fresh `main`, exact-head CI, `local-agent/agent-control` status/results and `growclip/agent-control` supervisor status;
8. follow an already-active/pending equivalent task instead of queuing a duplicate;
9. if clean, continue from SSH bounded exec + transfer;
10. keep documenting each completed hardening slice before moving to the next tool.

Do not repeat ADB work unless fresh evidence shows a regression.
