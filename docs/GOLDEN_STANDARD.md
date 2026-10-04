# Local Agent Golden Standard

The current source and production release is `v4.20.6` with Chat Bridge `0.8.1`. The immutable release tag points to `48eb9d8b6c26a9dfb317906d5099acabce8719c8`; current `main` and the deployed `self_revision` may legitimately be later verified revisions on the same release line. Never infer deployment from a source checkout: read fresh daemon status.

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
- Emergency disable/cancel controls remain authoritative over new work and active work according to their existing contracts.

## Queue deduplication

- Production parallel workers coalesce equivalent pending work before execution.
- A canonical explicit `dedupe_key` is branch-scoped and represents one logical intent.
- Without an explicit key, deterministic execution effects are fingerprinted.
- Active admission receipts are claim-aware; when the durable claim disappears, they stop blocking corrective work.
- Recent completed intent/effect receipts are bounded in time.
- Suppressed duplicates publish terminal `duplicate_task_suppressed` evidence pointing at the original task.
- Dedupe is a fail-safe, not permission for planners to spam the queue. The parent planner must inspect active/pending/recent work before creating another task.

## Superchat / Conversation Fabric invariants

- A managed ChatGPT conversation is transport/scheduling identity, not repository execution binding.
- One Superchat parent owns orchestration and the final execution decision.
- Children receive bounded goals plus pinned repository evidence and return bounded reasoning/evidence.
- Children have no `.agent/tasks` authority.
- Production child conversations run in normal tabs of the operator's already authenticated primary Chrome session with the installed Chat Bridge. Conversation Fabric must not launch a second Chrome process or maintain a separate production browser profile for child work.
- Child isolation is logical, not browser-profile isolation: exact child URL, tab id, spawn transaction, request digest and lifecycle state identify ownership. Ambiguous ownership still fails closed.
- Existing authenticated browser state is reused. Normal child creation must never require a second ChatGPT login, profile migration, cookie copy, manual Cloudflare loop or isolated-session recovery.
- Isolated Chromium/profile automation remains allowed for synthetic tests and CI only; it is not the production Conversation Fabric transport.
- Composer/readiness checks remain bounded and fail closed before submission.
- Conversation Operator intake is explicit configuration and should remain disabled at rest unless an active bounded campaign intentionally enables it.
- No second scheduler, direct model-execution loop or Native Messaging execution authority is introduced by Superchat.

## Chat Bridge invariants

- Chat Bridge is the browser-side authority for normal Chrome tab creation, content-script injection, child bootstrap delivery and tab-scoped lifecycle operations.
- GitHub-backed conversation control uses the exact conversation identity and monotonic `control_generation` for schedule mutations.
- Terminal conversation exhaustion remains fail-closed and cannot be resurrected by stale desired state.
- The global Bridge Master is not modified through per-conversation desired state.
- Bootstrap/wake prompts remain bounded; historical chat text is not copied wholesale into recurring prompts.

## Release/runtime invariants

- `local_agent.version.RELEASE_VERSION` names the release line.
- `vX.Y.Z` tags are immutable release anchors; moving `main` is read independently.
- Behavior-changing release candidates require matching release notes/changelog before a new version is frozen.
- Post-release patches on the same version line must be explicit in the checkpoint and verified by exact-head CI before merge/deploy.
- Fresh production acceptance requires both `daemon_version` and exact `self_revision` evidence.
- Candidate worktrees/branches are disposable and never become source of truth merely because they exist.

## Live acceptance standard

A Superchat acceptance is successful only when one parent conversation demonstrably delegates bounded reasoning to children opened in the existing primary Chrome session, receives their outputs, synthesizes the decision, and—if execution is needed—causes exactly one target-bound Local Agent task to run. No child may execute commands, no secondary production browser/profile may be created, no ambiguous tab ownership may be adopted, and no duplicate expensive task may run.
