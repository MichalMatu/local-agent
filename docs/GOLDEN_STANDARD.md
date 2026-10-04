# Local Agent Golden Standard

The current source and production release is `v4.20.6`. The immutable Local Agent release tag points to `48eb9d8b6c26a9dfb317906d5099acabce8719c8`; post-release source may advance Chat Bridge or hardening behavior on that unchanged Local Agent release line. `main` and deployed `self_revision` may legitimately be later verified revisions on the same release line. Never infer deployment from a source checkout: read fresh daemon status.

## Authority and execution

- Local Agent is a deterministic executor, not a coding model.
- `.agent/tasks` is the only executable repository-work contract.
- Chat Bridge identity is transport/scheduling identity only. It never grants repository execution authority.
- Every executable task resolves its actual target through the canonical runtime catalog, requires `execution_enabled=true`, and requires the exact canonical target `agent_binding` to agree across catalog, registry/control identity, and task payload.
- Registry/control agreement without a matching canonical catalog record is not sufficient authority and fails closed.
- Repository reasoning context, donor repositories, host-ops scope and chat identity never substitute for target authorization.
- `local-agent` is not a permanently special-cased disabled target. Its current canonical catalog record is execution-enabled, so self-execution is legal only through the same catalog, binding, lease, resource and emergency-control gates as any other target. If the catalog disables it later, execution must stop accordingly.
- The supported `agentd.py` operational launcher requires the machine repository registry and fails closed when it is absent; the legacy single-repository loop is not an executable fallback.
- Child chats are reasoning-only and must never execute machine commands, create `.agent/tasks`, mutate repositories, or make the parent execution decision.
- Recognizable local Codex invocations are rejected before execution; mentions in search arguments and filenames are allowed. This planner policy is not a shell sandbox.
- Task ids/payloads are immutable within a repository; interrupted claimed work is never silently replayed.
- Terminal results are durably spooled before remote publication.

## Repository and scheduler invariants

- Production uses the bounded parallel multirepo supervisor with scheduler hard cap four; default effective concurrency remains conservative and resource-gated.
- `host-ops` is the explicit `multirepo` planner/host-operation scope. It does not erase target-repository execution boundaries.
- Repository leases prevent two workers from executing the same repository concurrently.
- Named hardware/external resources and the `machine` resource are admitted before execution.
- Emergency disable/cancel controls remain authoritative over new and active work according to their existing contracts.

## Queue deduplication

- Production parallel workers coalesce equivalent pending work before execution.
- A canonical explicit `dedupe_key` is branch-scoped and represents one logical intent.
- `dedupe_revision` defaults to 1 and requires an explicit key. A new task id with a higher revision may follow a completed attempt, including a failed attempt, without waiting for the completion TTL. It never bypasses an active claim.
- Different plans for the same queued/active intent, or a changed completed plan without a higher revision, produce terminal `dedupe_intent_conflict` evidence rather than being silently suppressed.
- Without an explicit key, deterministic execution effects are fingerprinted.
- Admission receipts include task identity. If a worker crashes after durable final-result publication but before writing the completion receipt, restart reconciliation promotes the matching admitted receipt from durable `result_published` run evidence instead of allowing equivalent work to execute again.
- Admission without matching durable completion evidence remains retryable rather than being falsely marked complete.
- Recent completed intent/effect receipts are bounded in time.
- Suppressed duplicates publish terminal `duplicate_task_suppressed` evidence pointing at the original task.
- Dedupe is a fail-safe, not permission for planners to spam the queue. The parent must inspect active/pending/recent work before creating another task.

## Superchat / Conversation Fabric invariants

- A managed ChatGPT conversation is transport/scheduling identity, not repository execution binding.
- One managed Superchat parent owns orchestration and the final execution decision.
- Children receive bounded reasoning goals and never obtain `.agent/tasks` or machine-command authority.
- Production children are ordinary tabs in the operator's already authenticated primary Chrome session with the installed Chat Bridge.
- Conversation Fabric must not launch a second production Chrome/Chromium process, create/migrate a separate ChatGPT profile, copy cookies, use CDP as another production browser-control plane, or require another ChatGPT/Cloudflare login.
- Child isolation is logical: exact parent URL, child URL, tab id, spawn transaction, request/bootstrap digests and durable local campaign state. Ambiguous ownership fails closed.
- Only an already managed parent conversation may issue a `LOCAL_AGENT_CF` delegate/collect control. An unmanaged tab or child tab must not recursively fan out.
- The dedicated `LOCAL_AGENT_CF` envelope is separate from legacy LAB controls. Conversation Fabric scheduling/pacing uses GitHub `conversation_controls`, not LAB schedule markers.
- Campaign creation is deduplicated, submit/recovery is bounded, results require stable repeated observation, and cleanup closes only exact owned child tabs.
- Campaigns and captured child results are durable in `chrome.storage.local`; restart/reload recovery must never replay an already-submitted child bootstrap merely because service-worker/session state was lost.
- The existing GitHub-control alarm performs normal campaign observation/collection while the parent and Master are enabled. Explicit collect is a recovery/inspection control for already-submitted children, not the normal polling mechanism and never permission to resubmit prompts.
- Terminal parent feedback uses a durable per-campaign delivery claim before crossing the send boundary. Definite no-send clears the claim; confirmed delivery records it; ambiguous delivery is consumed to preserve at-most-once semantics across service-worker restart.
- A new delegation for the same parent is rejected while an older terminal campaign still has undelivered feedback. Terminal selection must never allow an obsolete campaign to be replayed after a newer campaign becomes authoritative.
- This terminal at-most-once rule intentionally prefers a potentially missed terminal notification after an ambiguous crash over duplicate terminal delivery.
- Isolated Chromium/profile automation remains allowed for deterministic tests and CI only.
- No second scheduler, Native Messaging execution authority, direct OpenAI API reasoning loop, or Local Agent-to-browser RPC is introduced by Conversation Fabric.

## Chat Bridge invariants

- Chat Bridge is the browser-side authority for primary-Chrome child tab creation, content injection, bootstrap delivery, result observation and owned-tab cleanup.
- Existing `worker_spawn.js` transaction/claim primitives remain the source of truth for child tab ownership.
- GitHub-backed conversation control uses the exact conversation identity and monotonic `control_generation` for every schedule mutation.
- Terminal conversation exhaustion remains fail-closed and cannot be resurrected by stale desired state.
- The global Bridge Master is not modified through per-conversation desired state.
- Bootstrap/wake prompts remain bounded; historical chat text is not copied wholesale into recurring prompts.

## GitHub edits vs machine execution

- Use direct GitHub edits for repository/source/documentation changes when the intended diff is exact and repository CI is sufficient verification.
- Use Local Agent when the work genuinely requires machine-local commands, local builds/tests, devices, host state, or another target-specific local environment.
- A Local Agent task is still illegal until the actual target is resolved through the canonical runtime catalog, `execution_enabled` is true, and the exact canonical `agent_binding` is used.
- Conversation Fabric children never perform either kind of mutation; the parent owns source mutation, task publication, CI, merge, cleanup and final verdict.

## Release/runtime invariants

- `local_agent.version.RELEASE_VERSION` names the Local Agent release line.
- `vX.Y.Z` tags are immutable release anchors; moving `main` is read independently.
- A Bridge-only post-release patch may advance the manifest version on the same Local Agent release line, but current docs/changelog must state that explicitly.
- Behavior-changing candidates require exact-head CI before merge/deploy.
- Fresh production acceptance requires both `daemon_version` and exact `self_revision` evidence plus the installed Bridge version.
- Candidate worktrees/branches are disposable and never become source of truth merely because they exist.

## Live acceptance standard

A Superchat acceptance passes only when one managed parent visibly delegates at least two bounded, non-overlapping reasoning jobs into normal child tabs in the same existing Chrome session, receives stable results, preserves captured results across a worker/reload interruption, closes its exact owned child tabs, delivers terminal feedback at most once, survives a later reload/poll without replay, synthesizes the final decision itself and—only if execution is justified—causes at most one exact target-bound Local Agent task to run. No secondary production browser/profile, child machine authority, ambiguous tab adoption, LAB pacing fallback or duplicate expensive execution is acceptable.
