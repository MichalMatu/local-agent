# Changelog

This changelog records the current operationally relevant Local Agent release line. The release tag and `local_agent.version.RELEASE_VERSION` are the version source of truth. The complete changelog through v4.19.10 is preserved verbatim in [`history/CHANGELOG_THROUGH_V4.19.10.md`](history/CHANGELOG_THROUGH_V4.19.10.md); historical per-release notes remain available under `docs/`.

## v4.19.11

- Preserve terminal Chat Bridge safety state across GitHub desired-state reconciliation: `conversation_exhausted` remains terminal for the same hard binding and cannot be resurrected by schedule drift or a newer pacing generation.
- Keep `assistant_retry_exhausted` fail-closed for the already-applied generation while allowing a newer GitHub control generation to act as an explicit recovery decision.
- Make manual `Run now` respect confirmed conversation exhaustion instead of bypassing the terminal stop.
- Add focused regression coverage for same/new-generation reconciliation, alarm cleanup and manual-delivery blocking while retaining runtime schema 3, content protocol v13 and assistant guard v8.
- Turn Python coverage into a release gate at 70% and pin GitHub Actions dependencies to immutable revisions rather than mutable major-version tags.
- Close stale BUG-001 documentation against the shipped v4.18.5 guarded-entrypoint orphaned repository-lease recovery; the current production topology detects exact kernel lock holders, terminates only proven orphan holders and verifies lock release.
- Advance Chat Bridge to 0.6.2. Task schema, scheduler/resource semantics, hard binding, executor behavior, MCP boundary and Local Agent concurrency are unchanged.

## Earlier releases

The full v4.19.10-and-earlier history is preserved in [`history/CHANGELOG_THROUGH_V4.19.10.md`](history/CHANGELOG_THROUGH_V4.19.10.md). Release-specific evidence remains in `RELEASE_NOTES_V*.md`.
