# Local Agent 4.18.20

## Summary

Prevent ChatGPT planner conversations from silently delegating Local Agent work to a local Codex CLI. ChatGPT remains the only planning/coding agent in the Local Agent flow; Local Agent remains a deterministic executor for declared commands, builds, tests and device operations.

## Policy hardening

- Reject executable task command fields containing the `codex` token before claim/execution.
- Cover legacy `commands`, `verify_commands`, structured `steps`, and `verify_steps` through the shared task-contract validation path.
- Reject direct `codex`, absolute-path Codex binaries, and `npx @openai/codex` examples in regression tests.
- Keep patch/write payload data unaffected; the restriction applies to executable command strings.
- Update the canonical Chat Bridge runtime example and live `chat-bridge-state` prompts so planners are explicitly told not to invoke or delegate work to local Codex or another local coding-agent/LLM CLI.

## Architecture boundary

The change closes a planner/executor loophole rather than adding a new planning layer. ChatGPT owns diagnosis, planning and coding decisions. Local Agent executes deterministic operations and returns evidence. A task that attempts to invoke local Codex is rejected as invalid task input before any task command runs.

## Downstream documentation audit

The registered downstream planner documents were reviewed before release: LiteGraph, Growbox ML Controller (`main` and `mvp/environment-controller`), MatrixHub (`main` and `develop`), and Tracker (`main`). They already define ChatGPT/the sandbox as the planner or software worker and Local Agent as the deterministic/local-machine executor, and none instructs Local Agent to launch Codex. No downstream file contradicts the hardened runtime contract, so no downstream repository edit is required for this release.

## Live mitigation and rollout

Before the source release, `chat-bridge-state` was updated with the planner-side prohibition in runtime commit `0d40c99f268d0925865701942297395e414e9fc7`. The source release adds executor-side fail-closed validation so the restriction does not depend only on prompt compliance.

The scheduler, resource model, hard repository binding, command watchdogs, result schema, Bridge extension code and content protocol are unchanged.
