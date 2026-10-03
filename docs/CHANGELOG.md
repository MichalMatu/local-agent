# Changelog

This changelog records the current operationally relevant Local Agent release line. The release tag and `local_agent.version.RELEASE_VERSION` are the version source of truth. The complete changelog through v4.19.10 is preserved verbatim in [`history/CHANGELOG_THROUGH_V4.19.10.md`](history/CHANGELOG_THROUGH_V4.19.10.md); historical per-release notes remain available under `docs/`.

## v4.20.0

- Add the accepted end-to-end Conversation Fabric child lifecycle with bounded multi-child delegation, durable result evidence, terminal/adoption/retirement recovery and exact owned-tab cleanup.
- Add a GitHub-backed operator control namespace under `.agent/conversation/requests/` and `.agent/conversation/results/` without changing executable `.agent/tasks` semantics or introducing a second scheduler/control transport.
- Add default-disabled supervisor intake that stages bounded operator requests under short control leases while long browser campaigns run outside repository/resource leases.
- Harden operator result publication with immutable request digests, restart-safe local spooling, post-sync identity validation and fresh-origin request/result proof before local spool deletion.
- Preserve the Local Agent 4.19.12 bounded Git transport retry, 20-second attempt cap and process-local circuit-breaker behavior in the merged release line.
- Advance Chat Bridge to 0.7.0 for the bounded Conversation Fabric child-spawn actuator while retaining runtime schema 3, content protocol v13 and assistant guard v8.
- Keep child chats reasoning-only: no independent machine authority, no direct OpenAI API reasoning loop and no MCP/second-scheduler Conversation Fabric control plane.
- Keep operator intake disabled unless its explicit Conversation Fabric runtime paths and enable flag are configured.

## v4.19.12

- Bound GitHub-backed control Git attempts to 20 seconds even when legacy callers request larger timeouts.
- Reduce transient Git retry inside one control-plane operation to one retry after 2 seconds; longer recovery remains owned by the existing scheduler backoff.
- Add a process-local 30-second circuit breaker to repeated control checkout synchronization after an exhausted transient Git failure.
- Reduce remote `operator-control` ref probing to a 5-second timeout and back off degraded probes for 5, 10, then 15 seconds while preserving the last known operator state and emergency-control responsiveness.
- Keep authentication, rebase/conflict and malformed reachable operator state handling unchanged and fail-closed where previously required.
- Add focused regression coverage for timeout capping, circuit opening/recovery and remote-operator probe backoff.
- No task schema, hard-binding, resource classification, concurrency, MCP or Chat Bridge protocol changes.

## v4.19.11

- Preserve terminal Chat Bridge safety state across GitHub desired-state reconciliation: `conversation_exhausted` remains terminal for the same hard binding and cannot be resurrected by schedule drift or a newer pacing generation.
- Keep `assistant_retry_exhausted` fail-closed for the already-applied generation while allowing a newer GitHub control generation to act as an explicit recovery decision.
- Make manual `Run now` respect confirmed conversation exhaustion instead of bypassing the terminal stop.
- Add focused regression coverage for same/new-generation reconciliation, alarm cleanup and manual-delivery blocking while retaining runtime schema 3, content protocol v13 and assistant guard v8.
- Turn Python coverage into a release gate at 70% and pin GitHub Actions dependencies to immutable revisions rather than mutable major-version tags.
- Close stale BUG-001 documentation against the shipped v4.18.5 guarded-entrypoint orphaned repository-lease recovery; the current production topology detects exact kernel lock holders, terminates only proven orphan holders and verifies lock release.
- Advance Chat Bridge to 0.6.2. Task schema, scheduler/resource semantics, hard binding, executor behavior, MCP boundary and Local Agent concurrency are unchanged.
- Complete the bounded live GitHub-control browser gate and return the managed conversation to PAUSED before the release decision.

## Earlier releases

The full v4.19.10-and-earlier history is preserved in [`history/CHANGELOG_THROUGH_V4.19.10.md`](history/CHANGELOG_THROUGH_V4.19.10.md). Release-specific evidence remains in `RELEASE_NOTES_V*.md`.
