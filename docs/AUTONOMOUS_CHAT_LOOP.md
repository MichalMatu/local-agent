# Autonomous Chat Planner Loop

This document defines the current autonomous loop connecting a managed parent Superchat, Chat Bridge `0.8.2`, GitHub desired state, browser-native Conversation Fabric child reasoning and deterministic Local Agent execution.

## Ownership

```text
ChatGPT parent       planner / synthesis / final execution decision
Chat Bridge          normal Chrome wake + Conversation Fabric child-tab transport
GitHub               durable conversation desired state + task/evidence transport
Local Agent           deterministic bounded executor
Target repository    source/work result
```

The ChatGPT DOM is not a scheduling source of truth and chat identity is not repository execution authority.

## Conversation transport and repository scope

Every configured conversation has one concrete Bridge chat identity for transport/scheduling. Active user goals or durable requests may reason across donor and target repositories without chat rebind.

Every executable Local Agent task still uses the exact canonical `agent_binding` of its actual target repository. An execution-disabled target such as `local-agent` may be inspected/edited through direct GitHub operations but must not receive a Local Agent task. `host-ops` remains an explicit host-operation/multirepo scope and its binding is never inherited by another target repository.

## GitHub-only pacing

For a managed conversation with an exact `conversation_controls` record, GitHub is authoritative for `STATUS`, `PAUSE`, `RESUME`, `NEXT` and `INTERVAL` semantics. Every schedule mutation increments `control_generation`; status reads do not.

Do not emit assistant LAB schedule markers for normal managed-chat pacing or Conversation Fabric continuation. They remain compatibility-only.

A bounded one-shot continuation uses:

```text
control_generation += 1
enabled = true
next_wake_at = exact offset-aware future timestamp
```

Completion/pause uses:

```text
control_generation += 1
enabled = false
next_wake_at = null
```

The global Bridge Master switch is independent operator state and must never be changed by conversation desired state.

## Browser-native Conversation Fabric

A managed parent may delegate reasoning by ending its assistant reply with one exact `LOCAL_AGENT_CF` block. Chat Bridge validates the exact parent tab/conversation, creates ordinary child tabs through the existing `worker_spawn.js` primitives, and keeps campaign/dedupe state in `chrome.storage.session`.

Children are reasoning-only and receive no Local Agent task or machine-command authority. Child results are bounded and must be stable before adoption. Completed/failed campaign cleanup closes only exact owned child tabs.

When Bridge asks for another collection attempt, the parent updates GitHub `conversation_controls` for a bounded future wake. On that wake the parent emits the exact collect block. No second Chrome/profile, CDP production control plane, Native Messaging, cookie migration, second scheduler or isolated ChatGPT login is part of the normal flow.

## Planner turn

At every user or Bridge wake:

1. identify the exact parent conversation and active goal;
2. inspect only evidence needed for the next decision;
3. check active/pending/recent work before queueing equivalent work;
4. use direct GitHub edits when an exact diff plus CI is enough;
5. use Local Agent only for local commands/builds/tests/devices/machine state in the actual execution-enabled target;
6. use Conversation Fabric children only for bounded parallel reasoning, not machine execution;
7. verify exact commit/result evidence before declaring completion;
8. choose one continuation state: complete, pause, bounded next wake, or exact-task cancellation.

## Local Agent task discipline

One parent goal should not create overlapping equivalent target tasks. Every task must use the target repository's exact runtime-catalog binding and, when cross-chat overlap is possible, a stable branch-scoped `dedupe_key`.

If evidence proves an active task cannot achieve its goal, issue exact repository-scoped cancellation and wait for durable cancellation/result evidence before replacement. Resource/capacity waiting is a continuation state, not completion.

## Wake delivery

Chat Bridge polls GitHub desired state, reconciles exact conversation/generation state and schedules the managed parent alarm. Wake delivery remains fail-closed: exact preferred tab/conversation, generation state, assistant idle state, empty/unmodified composer, live Send control and exact submitted-user confirmation are required.

The extension stores no GitHub credential and never writes GitHub desired state itself.

## Release/verification loop

For Bridge/runtime behavior changes:

1. isolate a branch from current `main`;
2. add focused positive/negative tests plus browser/DOM coverage when the content boundary changes;
3. run exact-head full CI, including browser and macOS smoke;
4. update current release/changelog/contracts;
5. re-run exact-head CI after the final metadata commit;
6. merge only with no blocking review;
7. verify deployed source/revision/version and reload the unpacked Bridge when required;
8. run one bounded live acceptance in normal Chrome;
9. leave the managed conversation paused unless continued automation is explicitly required.

## Canonical references

- `docs/GITHUB_BRIDGE_CONTROL.md` — managed conversation desired-state contract;
- `docs/conversation_fabric/README.md` — browser-native child reasoning surface;
- `docs/HOST_OPS_MULTIREPO.md` — host/multirepo execution boundary;
- `docs/CHATGPT_DOM_CONTRACT.md` — browser DOM compatibility boundary;
- `docs/GOLDEN_STANDARD.md` — release/runtime invariants;
- `docs/OPERATIONS.md` — operating procedure and live acceptance.
