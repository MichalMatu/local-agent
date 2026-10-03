# Changelog

This changelog records the current operationally relevant Local Agent release line. The release tag and `local_agent.version.RELEASE_VERSION` are the version source of truth. The complete changelog through v4.19.10 is preserved verbatim in [`history/CHANGELOG_THROUGH_V4.19.10.md`](history/CHANGELOG_THROUGH_V4.19.10.md); historical per-release notes remain available under `docs/`.

## v4.20.5

- Finalize the transport-only Superchat rollout: fix popup `Add current chat` after repository selection was removed from normal onboarding.
- Reduce Bridge bootstrap/wake payloads to the stable chat envelope plus runtime prompt, avoiding repeated catalog/binding policy text in user-visible turns.
- Match assistant delivery-error ownership by the stable chat envelope after prompt simplification.
- Keep legacy add/rebind/planner-scope metadata only as compatibility state; it is not normal repository routing or execution authority.
- Preserve the real security boundary: executable `.agent/tasks` still require the exact canonical `agent_binding` of the actual target repository and remain subject to registry/control identity, execution-enabled, lease/resource and emergency-control admission.
- Advance Chat Bridge to 0.8.1. No task schema, executor binding, resource, concurrency or child machine-authority expansion.

## v4.20.4

- Decouple Superchat conversation transport/scheduling identity from repository execution binding; normal multirepo and donor/target reasoning no longer requires Bridge rebind.
- Add operator request schema v3 with ordered `repository_ids` reasoning context while preserving v1/v2 compatibility and removing target execution-identity injection from Conversation Fabric campaigns.
- Advance Chat Bridge to 0.8.0; admit concrete managed chats without a repository binding selection and make GitHub conversation schedule ownership chat-scoped.
- Retain legacy rebind only as compatibility metadata/epoch refresh so stale-generation and race guards remain intact.
- Preserve the real security boundary: every executable `.agent/tasks` payload still requires the exact canonical `agent_binding` of its target repository and remains subject to registry/catalog/origin/execution admission.

## v4.20.3

- Add an explicit fail-closed `rebind-checkout` DEV-lab operation for moving an already adopted, unused Conversation Fabric lab marker from its original isolated checkout identity to one intended isolated operator checkout.
- Require the existing marker to be canonical and healthy, the new checkout to exist as a regular production-disjoint directory, and all mutable lab state directories to remain empty before the marker can change.
- Mutate only the atomic `lab.json` marker; preserve the browser profile and all browser-profile bytes unchanged.
- Keep profile adoption, checkout rebind, Superchat onboarding and operator-intake activation as separate explicit actions.
- Keep Chat Bridge at 0.7.0 and operator intake default-disabled.

## v4.20.2

- Add an explicit fail-closed `adopt-profile` DEV-lab operation for one pre-existing isolated Chromium `browser-profile` so a previously authenticated Conversation Fabric profile can be reused without copying production/daily Chrome state or repeating the login loop.
- Require an unmarked lab root containing exactly `browser-profile`, a regular Chromium `Local State`, at least one regular profile `Preferences` file and no symbolic links anywhere inside the adopted profile before any lab metadata is written.
- Preserve the existing browser profile bytes during adoption; create only the missing inert lab directories plus the exact `lab.json` layout marker.
- Keep ordinary `init` behavior unchanged: arbitrary non-empty unmarked roots remain rejected and cannot be silently adopted.
- Keep Chat Bridge at 0.7.0 and Conversation Fabric operator intake default-disabled; profile adoption, Superchat onboarding and intake activation remain separate explicit actions.

## v4.20.1

- Extend Conversation Fabric operator requests with schema v2 and one explicit canonical `repository_id`, while preserving legacy schema v1 compatibility.
- Resolve the requested target only through the runtime repository registry plus canonical binding catalog; reject disabled, mismatched or non-GitHub target identity and pin child reasoning to the target default-branch remote SHA.
- Keep child chats reasoning-only and preserve `.agent/tasks` as the only executable repository-work contract with the exact target repository binding.
- Keep Chat Bridge at 0.7.0 with runtime schema 3, content protocol v13 and assistant guard v8; no Bridge code or production Chrome behavior changes.
- Keep Conversation Fabric operator intake default-disabled; production activation and Superchat onboarding remain explicit post-install decisions.

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
