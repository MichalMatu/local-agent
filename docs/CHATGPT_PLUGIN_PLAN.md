# ChatGPT plugin plan

Status: candidate work on `feature/chatgpt-plugin-github-control-plane`.

## Goal

Expose the established Local Agent Git-backed control plane as a ChatGPT plugin workflow without adding a Local Agent MCP execution server.

The intended architecture is:

```text
ChatGPT planner
    -> Local Agent plugin skill
    -> existing connected GitHub app
    -> repository agent-control branch
    -> Local Agent executor on the user's computer
    -> run/result evidence through GitHub
```

The executor remains unchanged and retains hard binding, immutable tasks, bounded process execution, resource admission, watchdogs, recovery, and emergency controls.

## Confirmed platform facts on 2026-09-25

1. OpenAI plugins may contain reusable skills, connected apps, or both.
2. Local/workspace plugin packages may reference an eligible registered connector in `.app.json`. The existing ChatGPT GitHub app is currently exposed as an eligible connector and can therefore be required by the private prototype.
3. Local plugin marketplaces are supported by the ChatGPT desktop app and are suitable for private authoring/testing.
4. Public directory submission currently does **not** allow third-party publishers to publish an existing integration by reference. Public submission either accepts a skills-only package or requires the publisher to submit its own MCP server.
5. A public skills-only Local Agent plugin can preserve the no-MCP architecture if GitHub is installed/connected separately and the skill fails closed when GitHub write access is unavailable. This requires real end-to-end validation before release because the public plugin cannot currently auto-install the GitHub dependency by reference.
6. Plugin commerce currently does not allow selling digital subscriptions inside the plugin. Users may access an existing paid account/entitlement. Any future Local Agent billing and entitlement flow must therefore live outside the ChatGPT plugin surface.
7. Personal/local plugin authoring is documented primarily for ChatGPT Work/Codex/local desktop surfaces. Public plugins may be available from additional ChatGPT surfaces depending on plan and rollout. We must not claim that the final product uses ordinary Chat quota until that exact public surface is validated.

Primary OpenAI documentation:

- https://help.openai.com/en/articles/20001256-plugins-in-chatgpt-and-codex
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/plugins/build/skills
- https://developers.openai.com/plugins/deploy/submission-errors
- https://developers.openai.com/plugins/app-guidelines

## Phase 0 - private package scaffold

Implemented in this candidate branch:

- `plugins/local-agent/plugin.json` portable Agent Plugins manifest;
- `plugins/local-agent/.app.json` required GitHub connector mapping;
- `plugins/local-agent/skills/local-agent-control/SKILL.md` Git-backed control workflow;
- `.agents/plugins/marketplace.json` repository-local development marketplace;
- structural package regression tests.

No executor/runtime behavior changes are part of Phase 0.

## Phase 1 - private end-to-end validation

Use an isolated candidate checkout/worktree. Do not move the production `~/local-agent` checkout away from `main` merely to test the plugin.

Validate in the ChatGPT desktop app:

1. The repo marketplace is discovered.
2. `local-agent@local-agent-dev` installs.
3. Installation recognizes the required GitHub connection.
4. A read-only prompt activates the skill and reads one explicitly selected repository's `agent-control` state.
5. The skill refuses a missing/unauthorized repository instead of guessing.
6. The skill reads the exact `.agent/binding.json` before any task write.
7. The skill creates one immutable read-only task with exact binding and explicit `resources`.
8. Local Agent claims and executes that task on the user's computer.
9. The same conversation reads the exact terminal `.agent/results/<task-id>.json` and reports it correctly.
10. A second task for the same active goal is not queued while the first is active.
11. Exact-task `cancel_task` is tested with remote ACK plus terminal cancellation evidence.

Prefer a disposable test repository or a deliberately harmless read-only task for the first live run.

## Phase 2 - workflow hardening

After the first live E2E succeeds:

- split the single skill only if activation or workflow quality shows a real need;
- add representative positive/negative plugin evaluation prompts;
- add package validation for every required control-plane invariant;
- test direct GitHub edit + Local Agent read-only verification as the default hybrid development workflow;
- verify permission prompts for GitHub writes are understandable and do not create accidental task duplication;
- document recovery when GitHub write succeeds but the local executor is offline;
- document recovery when a task is accepted but terminal evidence is delayed;
- preserve the rule that Local Agent task/result evidence is authoritative for local execution.

## Phase 3 - public skills-only candidate

Create a separate public packaging profile that excludes `.app.json` and therefore does not publish the GitHub connector by reference.

The public skill must:

- state GitHub as a prerequisite without pretending installation grants it;
- use GitHub when available;
- stop with a clear prerequisite message when GitHub is not connected or lacks write access;
- never fall back to an untrusted alternate transport;
- retain exact repository/binding/task safety semantics.

Submit only after confirming the public plugin can run on the target ChatGPT surface and after checking current OpenAI submission requirements again.

## Phase 4 - product and entitlement

The execution transport should remain GitHub-backed unless evidence shows a real need for another transport.

If Local Agent becomes a paid product, use an external account/license flow for the Local Agent installation. The ChatGPT plugin may recognize an existing entitlement but must not sell or promote a digital subscription inside the plugin under current OpenAI policy.

A small entitlement service may be added later, but it is independent of the GitHub execution transport and is not an MCP requirement.

## Release boundary

This plugin work is additive infrastructure. Do not change Local Agent runtime behavior, task schema, binding semantics, or downstream project instructions merely to satisfy plugin packaging. Any future change to those contracts must follow the normal candidate-release, verification, downstream-audit, and versioning rules in `AGENTS.md`.
