# Local Agent Golden Standard

The current source and production release is `v4.20.6`. The immutable Local Agent release tag points to `48eb9d8b6c26a9dfb317906d5099acabce8719c8`; the current post-release source candidate advances Chat Bridge to `0.8.3` on that unchanged Local Agent release line. `main` and deployed `self_revision` may legitimately be later verified revisions on the same release line. Never infer deployment from a source checkout: read fresh daemon status.

## Authority and execution

- Local Agent is a deterministic executor, not a coding model.
- `.agent/tasks` is the only executable repository-work contract.
- Every executable task requires the exact canonical `agent_binding` of the actual target repository.
- Repository reasoning context, donor repositories and chat identity never grant execution authority.
- Child chats are reasoning-only and must never execute machine commands independently.
- Executable task command strings containing the `codex` token are rejected before execution.
- Task ids/payloads are immutable within a repository; interrupted claimed work is never silently replayed.
- Terminal results are durably spooled before remote publication.

## Repository and scheduler invariants

- Production uses the bounded parallel multirepo supervisor with scheduler hard cap four; default effective concurrency remains conservative and resource-gated.
- `host-ops` is the explicit `multirepo` planner/host-operation scope. It does not erase target-repository execution boundaries.
- Repository leases prevent two workers from executing the same repository concurrently.
- Named hardware/external resources and the `machine` resource are admitted before execution.
- `local-agent` remains execution-disabled as a normal task target unless an explicit future policy change says otherwise.
- Emergency disable/cancel controls remain authoritative over new and active work according to their existing contracts.

## Queue deduplication

- Production parallel workers coalesce equivalent pending work before execution.
- A canonical explicit `dedupe_key` is branch-scoped and represents one logical intent.
- Without an explicit key, deterministic execution effects are fingerprinted.
- Active admission receipts are claim-aware; when the durable claim disappears, they stop blocking corrective work.
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
- Isolated Chromium/profile automation remains allowed for deterministic tests and CI only.
- No second scheduler, Native Messaging execution authority, direct OpenAI API reasoning loop, or Local Agent-to-browser RPC is introduced by Conversation Fabric.

## Chat Bridge invariants

- Chat Bridge is the browser-side authority for primary-Chrome child tab creation, content injection, bootstrap delivery, result observation and owned-tab cleanup.
- Existing `worker_spawn.js` transaction/claim primitives remain the source of truth for child tab ownership.
- GitHub-backed conversation control uses the exact conversation identity and monotonic `control_generation` for every schedule mutation.
- Terminal conversation exhaustion remains fail-closed and cannot be resurrected by stale desired state.
- The global Bridge Master is not modified through per-conversation desired state.
- Bootstrap/wake prompts remain bounded; historical chat text is not copied wholesale into recurring prompts.

## Release/runtime invariants

- `local_agent.version.RELEASE_VERSION` names the Local Agent release line.
- `vX.Y.Z` tags are immutable release anchors; moving `main` is read independently.
- A Bridge-only post-release patch may advance the manifest version on the same Local Agent release line, but current docs/changelog must state that explicitly.
- Behavior-changing candidates require exact-head CI before merge/deploy.
- Fresh production acceptance requires both `daemon_version` and exact `self_revision` evidence plus the installed Bridge version.
- Candidate worktrees/branches are disposable and never become source of truth merely because they exist.

## Live acceptance standard

A Superchat acceptance passes only when one managed parent visibly delegates at least two bounded, non-overlapping reasoning jobs into normal child tabs in the same existing Chrome session, receives stable results, closes its owned child tabs, synthesizes the final decision itself and—only if execution is justified—causes at most one exact target-bound Local Agent task to run. No secondary production browser/profile, child machine authority, ambiguous tab adoption, LAB pacing fallback or duplicate expensive execution is acceptable.
