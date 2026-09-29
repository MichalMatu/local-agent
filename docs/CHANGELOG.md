# Changelog

This changelog records current operationally relevant Local Agent releases. Git tags and `local_agent.version.RELEASE_VERSION` are the release-version source of truth. Detailed release evidence remains in `docs/RELEASE_NOTES_V*.md`; older changelog text remains available in Git history.

## v4.19.9

- Promote Chat Bridge 0.6.0 and move normal managed-conversation `STATUS`, `PAUSE`, `RESUME`, `NEXT` and `INTERVAL` authority from assistant DOM markers to GitHub `conversation_controls` desired state on `chat-bridge-state`.
- Keep runtime schema 3 backward-compatible, add exact conversation/repository/binding/revision validation, monotonic `control_generation`, binding-scoped/local-generation idempotence and repair of local pacing drift.
- Ensure every MV3 worker activation owns a dedicated one-minute GitHub-control alarm so a remotely paused conversation can discover later `RESUME` without a conversation wake alarm.
- Keep GitHub credentials out of the extension; the Bridge reads the existing public runtime endpoint and never changes the global Master switch.
- Make legacy LAB schedule/operator pacing controls no-ops for GitHub-managed conversations while retaining explicit binding and maintenance migration paths.
- Complete daily-Chrome live E2E: PAUSE gen1 -> RESUME gen2 -> exact two-minute NEXT gen3 -> successful composer/Send wake -> PAUSE gen4; final desired state is PAUSED.
- Retain content protocol v13 and assistant guard v8; narrow the DOM contract to browser delivery/generation/error facts rather than scheduling authority. See `RELEASE_NOTES_V4.19.9.md`, `GITHUB_BRIDGE_CONTROL.md` and `CHAT_BRIDGE_HANDOFF_2026-09-30.md`.

## v4.19.8

- Fixed assistant LAB control discovery for assistant-only grouped ChatGPT turns and expanded structured assistant error recovery to `Resume stream unavailable`.
- Advanced Chat Bridge to 0.5.18 and assistant guard v8 while keeping content protocol v13.
- Hardened Host Ops recovery/diagnostic-browser stop against active ChatGPT generation.

## v4.19.7

- Fixed a newer user-only grouped turn shadowing the preceding assistant control and advanced Bridge/content metadata accordingly.

## v4.19.6

- Merged explicit and grouped assistant representations by logical turn/document order so newer grouped assistant turns were not hidden by older explicit nodes.

## v4.19.5

- Added fail-closed grouped-turn assistant fallback for renderer variants without an explicit assistant role marker.

## v4.19.4

- Fixed mixed legacy/current ChatGPT role-family ordering and added focused real-extension coverage.

## v4.19.3

- Adapted Bridge discovery to the then-current `data-conversation-role` / `data-user-message-bubble` renderer shape.

## v4.19.2

- Added bounded task-scoped external payload-file transport while preserving task digesting, schema and execution safety.

## v4.19.1

- Added fail-closed `planner_scope`, including the canonical `host-ops` multirepo operator workspace, while preserving exact target-repository binding at execution time.

## v4.19.0

- Released generic Local Agent-owned MCP support through the official Python SDK with loopback-only Streamable HTTP, explicit local risk policy and bounded results/artifacts.

## Earlier releases

Detailed records for v4.18.x and earlier remain in `docs/RELEASE_NOTES_V*.md` and repository Git history. Historical notes are evidence only; current behavior is defined by `main` plus the canonical operational documents.
