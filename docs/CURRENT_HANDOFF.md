# Current handoff — primary-Chrome Conversation Fabric pivot

Date: 2026-10-04

Status: Local Agent release line `v4.20.6` / Chat Bridge `0.8.1` remains the current production baseline. Queue deduplication and the prior child-browser readiness work are released. The live Superchat acceptance is intentionally paused because the production child transport assumption has changed: separate/isolated child browser profiles are rejected as the production design.

## Source of truth

Do not reconstruct state from old chats. Read fresh repository/runtime evidence in this order:

1. `AGENTS.md`
2. this file
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/conversation_fabric/CURRENT_PLAN.md`
6. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

Historical self-diagnostic, DEV-lab, isolated-profile and release documents remain evidence only; they are not the current implementation plan.

## Current baseline

- immutable release tag: `v4.20.6` -> release commit `48eb9d8b6c26a9dfb317906d5099acabce8719c8`;
- Local Agent version line: `4.20.6`;
- Chat Bridge: `0.8.1`;
- current `main`: always read fresh;
- production `daemon_version` and `self_revision`: always verify from fresh daemon status;
- `local-agent` itself remains execution-disabled as a task target.

## Architecture correction

The previous production assumption that Conversation Fabric should create/manage child chats inside a dedicated isolated Chromium profile is retired.

Observed failure mode: a second browser/profile does not reliably share the operator's established ChatGPT/Cloudflare authentication. Login challenges and Cloudflare verification therefore become part of normal child creation and can block the entire orchestration flow.

The accepted production model is now:

```text
operator's normal authenticated Chrome
  -> installed Chat Bridge
  -> parent Superchat tab
  -> child tabs in the same Chrome session
  -> logical tab/transaction ownership
  -> parent synthesis
  -> exact target .agent/tasks execution only when justified
```

Production Conversation Fabric must not launch a second Chrome process and must not require a separate ChatGPT browser profile. Isolation is provided by exact child URL, Chrome tab id, transaction id, request/bootstrap digests and durable lifecycle state—not by separate cookie/profile state.

Synthetic isolated Chromium remains valid for browser tests and CI only.

## Existing reusable implementation

The repository already contains the browser-side primitives needed for this pivot:

- Chat Bridge has `tabs` and `scripting` permissions in the normal Chrome extension;
- `chat_bridge/worker_spawn.js` already owns transaction-safe tab creation/recovery and bootstrap delivery primitives;
- Chat Bridge content scripts already perform bounded composer interaction in ordinary ChatGPT tabs;
- existing child ownership and canonical URL concepts remain valid.

Do not rebuild those capabilities in a second Playwright-controlled browser.

## Current blocker / next milestone

The current live actuator still launches a Playwright persistent context, so it does not yet satisfy the new production invariant. Replace that production path with primary-Chrome/Chat-Bridge tab control, retain synthetic isolated browser coverage for CI, and remove normal-flow login/profile migration from Conversation Fabric.

Only after that path is verified should the bounded live Superchat acceptance resume.

## Acceptance after the pivot

One parent must visibly delegate at least two narrow, non-overlapping reasoning jobs into child tabs in the existing Chrome session, collect their results, make the final decision itself and—only if justified—queue exactly one bounded executable task in the real target repository. Verify that duplicate execution does not occur.
