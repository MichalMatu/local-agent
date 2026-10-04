# Current handoff — browser-native Conversation Fabric

Date: 2026-10-04

Status: Local Agent remains on release line `v4.20.6`. The current post-release source uses Chat Bridge `0.8.3` and browser-native Conversation Fabric inside the operator's already authenticated primary Chrome session. The old isolated-profile/Playwright production assumption is retired.

## Source of truth

Read fresh repository/runtime evidence in this order:

1. `AGENTS.md`
2. this file
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/AUTONOMOUS_CHAT_LOOP.md`
6. `docs/GITHUB_BRIDGE_CONTROL.md`
7. `docs/conversation_fabric/CURRENT_PLAN.md`

Historical isolated-profile, DEV-lab, self-diagnostic, checkpoint and release-note documents are evidence only.

## Current authority model

- Chat Bridge conversation identity is transport/scheduling identity only. It never grants repository execution authority.
- Every executable Local Agent task resolves its actual target through the canonical runtime catalog, requires `execution_enabled=true`, and uses the target repository's exact canonical `agent_binding`.
- Registry/control agreement without a matching canonical catalog record fails closed.
- The current canonical catalog enables `local-agent`; self-execution therefore follows the same binding, lease, resource and emergency-control gates as every other target. There is no permanent special-case self-execution ban.
- The supported `agentd.py` launcher requires the machine repository registry and fails closed when it is absent; it does not fall back to the legacy single-repository executor loop.
- Use direct GitHub edits when an exact repository diff plus CI is sufficient. Use Local Agent only for work that genuinely requires machine-local commands, local builds/tests, devices or host state.
- Conversation Fabric children are reasoning-only. They do not create `.agent/tasks`, run machine commands, mutate repositories or make the final parent execution decision.

## Accepted production browser model

```text
normal authenticated Chrome
  -> managed parent Superchat tab
  -> installed Chat Bridge
  -> LOCAL_AGENT_CF delegate control
  -> existing worker_spawn.js ownership primitives
  -> ordinary reasoning-only child tabs in the same Chrome session
  -> stable child result capture into durable campaign state
  -> owned-tab cleanup
  -> terminal parent feedback at most once
  -> parent synthesis
  -> exact target .agent/tasks only when machine execution is justified
```

Production Conversation Fabric must not launch a second Chrome/Chromium process, maintain a separate ChatGPT profile, copy cookies, use CDP as a second browser-control plane, require another login, or treat Cloudflare recovery as normal orchestration.

Isolation is logical: exact parent conversation, tab id, child URL, spawn transaction, request/bootstrap digests and durable local campaign state. Ambiguous ownership fails closed.

## Conversation Fabric recovery and delivery

- Campaigns and captured child results are durable in `chrome.storage.local`.
- A submitted child survives service-worker restart/reload. Lost session ownership may be reconstructed only from the child page's exact transaction/request/bootstrap/current-URL claim; a reused tab id is never sufficient.
- Pre-submit/ambiguous spawning fails closed rather than replaying a child prompt.
- Stable results require the explicit completion marker plus repeated identical observation; each stable result is persisted before sibling completion or tab cleanup.
- Transient child observation failures remain pending and recoverable rather than becoming permanent child failures.
- The existing GitHub-control alarm normally observes/collects campaigns while the parent and Master are enabled. Explicit `collect` is a recovery/inspection operation for already-submitted children and must never resubmit their bootstrap prompts.
- Terminal feedback uses a durable per-campaign delivery claim before crossing the send boundary. A surviving ambiguous claim suppresses resend after restart, intentionally preferring a possibly missed terminal notification to duplicate terminal delivery.
- A new delegation for a parent is rejected while an older terminal campaign still has undelivered feedback, preventing stale cross-campaign terminal replay.
- Completed/failed campaign cleanup closes only exact owned child tabs.

## Runtime hardening now in `main`

The current source includes the audit repairs that:

- require canonical runtime-catalog admission for workers;
- fail closed when the operational daemon registry is absent;
- reconcile an admitted dedupe receipt from matching durable `result_published` run evidence after a crash, preventing equivalent work from being admitted again solely because the claim disappeared;
- prevent stale Conversation Fabric terminal replay across campaigns and settle nonterminal started/pending feedback without terminal-only ACK retries.

These are production-path invariants, not compatibility hints. New changes must preserve them and add regressions through the real consumer path whenever feasible.

## Task authoring and dedupe

- `python -m local_agent.cli.diagnostics prepare-task` compiles inline drafts using an explicit catalog target and execution profile, then writes the existing immutable task/payload bundle into a publication checkout.
- `validate-task --repository` adds read-only local admission preflight without weakening worker binding checks or taking execution leases.
- Corrective plans use a new task id and higher `dedupe_revision` after completion. Conflicting queued/active intents are reported as `dedupe_intent_conflict`; revisions never bypass an active claim.
- Local Codex invocation policy rejects recognizable invocations but is not a shell sandbox.

## Verification standard

For runtime or Bridge behavior changes:

1. start from current `main`;
2. add a regression reproducing the real production path;
3. run full exact-head CI, including browser and macOS smoke;
4. merge only with green jobs and an expected-head guard;
5. perform bounded live/real-browser acceptance when browser lifecycle/recovery semantics changed;
6. retire only branches proven fully merged.

Children receive bounded source context explicitly; the parent synthesizes results and owns any exact target-bound executable task. No automatic child-prompt replay is permitted after interrupted spawning.
