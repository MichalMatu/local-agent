# Local Agent Operations

This is the canonical operational workflow for `MichalMatu/local-agent`.

## Production/source baseline

```text
Local Agent release line: 4.20.6
immutable tag v4.20.6: 48eb9d8b6c26a9dfb317906d5099acabce8719c8
released Bridge at tag: 0.8.1
current source candidate Bridge: 0.8.11
```

`main` is a moving production source branch and may contain later verified post-release patches. Before any live operation, read fresh daemon status and verify `daemon_version`, `self_revision`, repository registry identity, execution variant and installed Bridge version.

Production bounded-parallel execution uses `agent_parallel.py` with a hard worker cap of four. Serial `agent_multirepo.py` remains a bounded fallback/diagnostic path, not a second production scheduler. It reuses safe queued-duplicate admission so equivalent queued work is not executed twice, but full production coalescing/reconciliation/crash-recovery semantics remain owned by the parallel path.

## Normal inspection order

1. Read `AGENTS.md` and `docs/CURRENT_HANDOFF.md`.
2. Read current `main` and the relevant immutable release/checkpoint SHA.
3. Read fresh daemon status from the operational repository.
4. Read only target repository status/task/result evidence needed for the next decision.
5. For Chat Bridge pacing, read the exact GitHub `conversation_controls` record; never infer scheduling from old chat text.

## Executable repository work

- Resolve the actual target repository from the runtime catalog/registry.
- Require its exact canonical `agent_binding` in `.agent/tasks`.
- Keep executable effects deterministic and bounded.
- Declare required machine/hardware resources explicitly.
- Use one stable branch-scoped `dedupe_key` for one logical intent when overlap is possible.
- Inspect pending/active/recent work before publishing another task.
- Children and Superchat transport never bypass this boundary.

### Draft preparation and admission preflight

Use the existing diagnostics CLI to compile an inline task draft without manually copying a binding UUID:

```sh
python -m local_agent.cli.diagnostics prepare-task draft.json \
  --repository growclip --profile repository \
  --output-dir /path/to/publication-checkout/.agent/tasks
python -m local_agent.cli.diagnostics validate-task \
  /path/to/publication-checkout/.agent/tasks/example.json --repository growclip
```

An inline draft can be as small as `{"id":"example","commands":["python -m unittest -q"]}`. The explicit target accepts a catalog id or `owner/name`; chat metadata is never consulted. Existing mismatched bindings are rejected rather than replaced. `repository` supplies `resources: []` when absent, `hardware` requires explicit named resources, and `host-maintenance` requires the `local-agent` target but defaults to `resources: []`. Host maintenance that needs a concrete external resource declares it explicitly (for example `browser:chrome` or `usb:esp32`); only true whole-host operations request `resources: ["machine"]`. The `machine` resource remains an exclusive global mutex and must be declared alone. Profiles compile to the existing task schema and keep its configured timeout and memory limits.

Preparation uses the existing atomic task-bundle writer and refuses to overwrite an existing manifest or write into a registered daemon control clone, including disabled entries and symlink aliases. Publish the manifest and its adjacent payload directory together through the target's remote `agent-control` branch. Preparation itself does not commit, push, enqueue or execute work.

`validate-task --repository` reports schema validity separately from local admission readiness. It checks emergency disable, catalog/registry/control/task identity, checkout origins and branch validity. `--catalog` and `--registry` select explicit local configuration files. Preflight is a read-only snapshot; resource and execution leases are still acquired by the executor at admission.

For a corrective plan or deliberate rerun after completion, publish a **new task id** with the same `dedupe_key` and an increased integer `dedupe_revision`. Changing commands under the same revision produces `dedupe_intent_conflict`; unchanged duplicates remain suppressed. A higher revision cannot bypass an active claim. Never reuse the old task id or automatically replay interrupted work.

### Timeout contract

`task_timeout` is the runtime's stage-admission execution budget. Its deadline starts before workspace preparation, so preparation time consumes the remaining budget. A command or verification stage starts only when its full stage timeout plus the 60-second finalization reserve still fits.

`task_timeout` is **not** a strict total wall-clock deadline. Durable checkpointing and cleanup keep their own bounded finalization rules and may finish after the execution deadline. This preserves recoverable dirty state instead of abandoning finalization at an arbitrary wall-clock boundary.

## Multi-repository / host operations

Host-maintenance work uses the `local-agent` target and the absorbed `local_agent.host_ops` capability layer. The standalone `host-ops` repository is not in the canonical execution catalog and must not receive executable tasks. A repository edit/build/test still belongs to its actual target repository and requires that target repository's own execution-enabled binding.

Never use `host-ops` to tunnel around a disabled target repository.

### Host Ops rollback contract

Rollback the maintained implementation only through `local-agent`. Never restore the standalone `MichalMatu/host-ops` repository to the canonical catalog or machine registry, never unarchive it as part of runtime recovery, and never reintroduce a second Host Ops scheduler/control plane.

Before rollback, record the exact source/deployed revision and current repository registry. Restore only to a previously verified **post-absorption** Local Agent revision. After the supported supervisor restart, require all of these checks before resuming host maintenance:

- `python -m local_agent.host_ops --json-contract-version` prints exactly `1`;
- `python -m local_agent.host_ops host profile --json` returns a valid bounded host profile;
- the canonical catalog and machine registry contain neither `host-ops` nor `MichalMatu/host-ops`;
- `local-agent` remains execution-enabled under binding `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`;
- fresh daemon status reports the expected `local-agent` repository identity and the restored exact revision.

Use `docs/CURRENT_HANDOFF.md` and the latest green post-absorption checkpoint as the rollback anchor. Do not roll back across the Host Ops absorption/retirement boundary.

## Superchat browser model

Production Conversation Fabric runs entirely inside the operator's existing authenticated primary Chrome session and installed Chat Bridge. Parent and child conversations are ordinary tabs in that same browser session.

The supported browser-native path is:

```text
managed parent assistant reply
  -> exact trailing LOCAL_AGENT_CF control block
  -> parent Conversation Fabric content controller
  -> Chat Bridge service worker
  -> existing worker_spawn.js chrome.tabs/chrome.scripting primitives
  -> child tabs
  -> stable child result capture
  -> exact owned-tab cleanup
  -> parent feedback/synthesis
```

Do not launch a second production browser/profile, use `chat-bridge-cft` as the acceptance browser, copy cookies, require a second login, loop on Cloudflare, attach a second production control plane with CDP, or add Native Messaging/browser RPC.

Isolated Chromium remains test-only for deterministic browser/DOM coverage.

## Conversation Fabric controls

A managed parent may emit one exact trailing control block:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"delegate","children":[...]}
LOCAL_AGENT_CF>>>
```

or later:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"collect","campaign_id":"cf-..."}
LOCAL_AGENT_CF>>>
```

The service worker admits controls only from the exact top-frame managed parent. Children are explicitly reasoning-only. Campaign state/dedupe is durable in local extension storage, results are bounded and must be stable across repeated observations, and only exact owned child tabs are closed.

## Chat Bridge pacing/control

Conversation Fabric does not use LAB schedule markers for normal pacing. Its existing minute GitHub-control alarm automatically collects child answers and delivers terminal feedback while the parent and Master are enabled. An explicit collect may recover an observation of already-submitted children without repeating prompts.

GitHub remains authoritative for remotely managed parent scheduling. Any change to its exact `conversation_controls` record must increment `control_generation`. Pause the parent after bounded acceptance unless continued automation is explicitly intended.

Never modify Bridge Master through conversation desired state.

## Operator observability

The normal Bridge popup is the single concise read-only status surface. Browser-owned facts come directly from the installed extension: Bridge manifest version, Master state, current-parent Fabric campaign, captured/vaulted result count, cleanup state and terminal-feedback delivery state.

Local Agent publishes a separate bounded `.agent/status/operator.json` through the existing supervisor control checkout. It contains deployed `daemon_version` / exact `self_revision`, Conversation Operator enabled/configured/running state, active workflow identity + child count, and bounded durable dedupe suppression/rejection/reconciliation evidence. It contains no child prompt text and grants no execution authority.

Runtime schema 3 may provide an optional `operator_status_url`. Chat Bridge accepts that URL only from `https://raw.githubusercontent.com`, reads it with bounded timeout/cache, and treats failure as telemetry-unavailable rather than as a scheduling/execution failure. Enable that URL in live runtime state only after the matching Local Agent publisher is deployed and the remote JSON exists.

## Live acceptance

The bounded arithmetic acceptance is recorded in `conversation_fabric/SAME_BROWSER_PROOF_2026-10-04.md`. For a fresh acceptance after verified code is loaded into the normal Chrome session:

1. verify exact source/deployed revision, Bridge `0.8.11`, parent URL/tab and GitHub control state;
2. delegate at least two narrow non-overlapping reasoning jobs from one managed parent;
3. visibly confirm both children open as normal tabs in the same Chrome session without another login/profile;
4. wait for automatic result collection on the existing control alarm;
5. collect stable results and confirm owned child tabs close;
6. parent reconciles results and makes the final decision;
7. if execution is justified, queue exactly one target-bound task with the target repository's canonical binding and stable dedupe key;
8. verify no equivalent duplicate execution;
9. end with the parent scheduling state intentionally paused unless ongoing automation is desired.

Stop rather than weakening checks if parent ownership, child ownership, result identity, repository binding or duplicate-execution status is uncertain.

## Release/checkpoint discipline

- Verify behavior-changing code on the exact candidate SHA before merge.
- Tags remain immutable anchors.
- After merge, allow guarded self-update/deployment to advance naturally and verify exact installed revision.
- Keep only `main`, `agent-control`, `chat-bridge-state`, `operator-control` and genuinely active short-lived work branches.
- Historical isolated-browser plans remain evidence only, not normal operating instructions.
