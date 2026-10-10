# Autonomous Chat Planner Loop

This document defines the managed-parent loop connecting Chat Bridge,
GitHub desired state, reasoning-child delegation and deterministic Local Agent
execution. Public `main` retains the legacy source baseline; the open
GitHub-first candidate uses Bridge `0.8.18` (PR #274). A **single** private
child E2E passed in the operator's real Chrome on 2026-10-10; this does not
validate private multi-child, cross-device ownership or restart recovery.
See [current GitHub-first handoff](conversation_fabric/GITHUB_FIRST_CURRENT_HANDOFF.md)
for the live proof and remaining gates.

## Ownership

```text
ChatGPT parent       planner / synthesis / final execution decision
Chat Bridge          normal Chrome wake + Conversation Fabric child-tab transport
GitHub               durable conversation desired state + task/evidence transport
Local Agent          deterministic bounded executor
Target repository    source/work result
```

The ChatGPT DOM is not a scheduling source of truth and chat identity is not repository execution authority.

## Conversation transport and repository scope

Every configured conversation has one concrete Bridge chat identity for transport/scheduling. Active user goals or durable requests may reason across donor and target repositories without chat rebind.

Every executable Local Agent task resolves the actual target through the canonical runtime catalog, requires `execution_enabled=true`, and uses that target repository's exact canonical `agent_binding`. Registry/control agreement without a canonical catalog record fails closed. The current catalog enables `local-agent`, so self-execution is allowed only through the same target-bound admission, lease, resource and emergency-control rules as any other repository. Cross-repository reasoning comes from the active goal/request, not from a special planner-scope repository. Host operations use the internal `local_agent.host_ops` subsystem through the `local-agent` target.

## GitHub-only pacing

For a managed conversation with an exact `conversation_controls` record, GitHub is authoritative for:

- `STATUS` reads;
- `PAUSE`;
- `RESUME`;
- `NEXT`;
- `INTERVAL`.

Every schedule mutation increments `control_generation`; status reads do not.

Do **not** emit assistant LAB schedule markers for normal managed-chat pacing or Conversation Fabric continuation. They remain compatibility-only.

A bounded one-shot continuation uses:

```text
control_generation += 1
enabled = true
next_wake_at = exact offset-aware future timestamp
```

For ordinary Local Agent task progress, a justified early re-check should be scheduled no sooner than about two minutes; normal multi-minute build/test work should usually be checked at 5-10 minutes rather than at 30-second cadence. Conversation Fabric child-result collection is not driven by parent-authored short polling: the existing GitHub-control alarm observes active campaigns while the parent and Master are enabled.

Completion/pause uses:

```text
control_generation += 1
enabled = false
next_wake_at = null
```

The global Bridge Master switch is independent operator state and must never be changed by conversation desired state.

## Browser-native Conversation Fabric

A managed parent may delegate reasoning by ending its assistant reply with one exact `LOCAL_AGENT_CF` block. Chat Bridge validates the exact parent tab/conversation, creates ordinary child tabs through the existing `worker_spawn.js` primitives, and stores durable campaign/result state in `chrome.storage.local`.

Children are reasoning-only and receive no Local Agent task or machine-command authority. They do not create `.agent/tasks`, execute machine commands, mutate repositories or make the parent decision. Child results are bounded and must be stable before adoption. Completed/failed campaign cleanup closes only exact owned child tabs.

Normal collection is worker-driven. The existing minute GitHub-control alarm reconciles GitHub conversation state and polls active Fabric campaigns while parent + Master are enabled. An explicit `collect` control is a bounded recovery/inspection operation for children whose prompts were already submitted; it is never permission to submit the bootstrap again.

Restart/reload recovery is durable:

- campaign state and each captured stable result survive service-worker restart in `chrome.storage.local`;
- submitted child tabs are reattached only when exact transaction, request digest, bootstrap digest and current child URL evidence agree;
- ambiguous/pre-submit spawning fails closed rather than replaying a prompt;
- transient observation failures remain pending and can recover later;
- results are persisted before sibling completion or owned-tab cleanup.

Terminal feedback is at-most-once across restart. Bridge persists a campaign-specific terminal delivery claim before crossing the parent send boundary. Definite no-send clears the claim; confirmed delivery records it; an ambiguous surviving claim is treated as consumed and is not resent after restart. This deliberately trades possible terminal-notification liveness for replay safety. A parent cannot start a different new delegation while an older terminal campaign still has undelivered feedback, preventing stale cross-campaign replay.

No second Chrome/profile, CDP production control plane, Native Messaging, cookie migration, second scheduler or isolated ChatGPT login is part of the normal flow.

## Planner turn

At every user or Bridge wake:

1. identify the exact parent conversation and active goal;
2. inspect only evidence needed for the next decision;
3. check active/pending/recent work before queueing equivalent work;
4. use direct GitHub edits when an exact repository diff plus CI is sufficient;
5. use Local Agent only for local commands/builds/tests/devices/machine state in the actual execution-enabled target;
6. for every Local Agent task, resolve the actual target from the canonical runtime catalog and use its exact binding;
7. use Conversation Fabric children only for bounded parallel reasoning, not machine execution;
8. verify exact commit/result evidence before declaring completion;
9. choose one continuation state: complete, pause, bounded next wake, or exact-task cancellation.

## Local Agent task discipline

One parent goal should not create overlapping equivalent target tasks. Every task must use the target repository's exact runtime-catalog binding and, when cross-chat overlap is possible, a stable branch-scoped `dedupe_key`.

Production parallel dedupe persists admission/completion evidence. If a crash occurs after durable final-result publication but before the completion receipt is written, restart reconciliation uses matching durable `result_published` run evidence to promote the admitted receipt rather than allowing equivalent work to execute again.

If evidence proves an active task cannot achieve its goal, issue exact repository-scoped cancellation and wait for durable cancellation/result evidence before replacement. Resource/capacity waiting is a continuation state, not completion.

## Wake delivery

Chat Bridge polls GitHub desired state, reconciles exact conversation/generation state and schedules the managed parent alarm. Wake delivery remains fail-closed: exact preferred tab/conversation, generation state, assistant idle state, empty/unmodified composer, live Send control and exact submitted-user confirmation are required.

The extension stores no GitHub credential and never writes GitHub desired state itself.

## Direct GitHub edits vs Local Agent

Use direct GitHub edits for repository inspection/source/docs work when the intended diff is exact and repository CI is sufficient verification. Use Local Agent for work that genuinely depends on the Mac or another target machine: local builds/tests, devices, local services, host state or environment-specific commands. Chat Bridge itself never upgrades transport identity into execution authority.

## Release/verification loop

For Bridge/runtime behavior changes:

1. isolate a branch from current `main`;
2. add focused positive/negative tests plus browser/DOM coverage when the content boundary changes;
3. run exact-head full CI, including browser and macOS smoke;
4. update current contracts/documentation;
5. re-run exact-head CI after the final metadata commit;
6. merge only with green jobs and an expected-head guard;
7. verify deployed source/revision/version and reload the unpacked Bridge when required;
8. run one bounded live/real-browser acceptance when lifecycle/recovery changed;
9. retire only branches proven fully merged;
10. leave the managed conversation paused unless continued automation is explicitly required.

## Canonical references

- `docs/GITHUB_BRIDGE_CONTROL.md` — managed conversation desired-state contract;
- `docs/conversation_fabric/README.md` — browser-native child reasoning surface;
- `docs/HOST_OPS_MULTIREPO.md` — retired standalone Host Ops identity and current multirepo reasoning boundary;
- `docs/CHATGPT_DOM_CONTRACT.md` — browser DOM compatibility boundary;
- `docs/GOLDEN_STANDARD.md` — release/runtime invariants;
- `docs/OPERATIONS.md` — operating procedure and live acceptance.
