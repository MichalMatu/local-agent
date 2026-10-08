# ChatGPT DOM contract for Chat Bridge

This document records the current **browser compatibility boundary** used by Chat Bridge `0.8.13` / content protocol `26`. Selectors are evidence, not ChatGPT product guarantees. Unsupported page shapes fail closed.

Normal pacing/status for a GitHub-managed conversation does **not** depend on assistant DOM parsing. GitHub desired state is authoritative for `STATUS`, `PAUSE`, `RESUME`, `NEXT` and `INTERVAL`.

Historical release notes describe earlier renderer assumptions and assistant-side LAB schedule transport. They are not the current scheduling contract.

## Release checkpoint

```text
Local Agent release line: 4.20.6
Chat Bridge:              0.8.13
content protocol:         26
assistant guard:          8
runtime schema:           3 + optional conversation_controls
```

Current browser-native Conversation Fabric runs in the operator's existing authenticated Chrome session. Isolated-profile browser tooling is test/development evidence only.

## What DOM still owns

DOM inspection is limited to facts that cannot be obtained from GitHub desired state:

- locating and writing the current composer;
- locating/re-resolving the live enabled Send control;
- detecting active generation from visible Stop controls;
- confirming the exact submitted user turn;
- recognizing bounded structured assistant Retry/error cards;
- detecting conversation-length exhaustion;
- discovering the latest bounded child assistant result for Conversation Fabric;
- explicit legacy binding/maintenance controls during migration.

Assistant-turn text must not decide whether a GitHub-managed chat is paused, resumed or scheduled.

## Composer and Send

Composer discovery uses bounded current/legacy selectors centered on `#prompt-textarea` and form-scoped contenteditable/textarea fallbacks.

Before automatic insertion:

- the exact conversation URL must match;
- generation must not be active;
- existing operator text blocks insertion unless it is the exact retained Bridge-owned prompt.

Immediately before submission Bridge re-resolves the current enabled Send button. The primary action is a live DOM `click()` on that current button; `form.requestSubmit()` is bounded fallback only. A stale button reference must never be trusted.

Successful delivery is confirmed only when the exact prompt appears as a newly submitted user turn. A click alone is not delivery evidence.

## User-turn discovery

Supported user representations include:

```text
[data-message-author-role="user"]
[data-user-message-bubble]
[data-turn-key] as logical turn identity fallback
```

These are used for submitted-user confirmation and ownership/retry boundaries, not repository identity.

`data-turn-key` is never a Bridge conversation id, repository id or agent binding.

## Assistant representations

Legacy compatibility code may observe:

```text
[data-message-author-role="assistant"]
[data-conversation-role="assistant"]
[data-turn-key]
```

Do not assume a role marker contains the assistant body. Live saved-page evidence showed `data-conversation-role="assistant"` attached to an accessibility heading containing only `ChatGPT said:` while the visible assistant body was a sibling in the same rendered unit.

That evidence is the reason normal scheduling authority moved out of assistant DOM text. Existing grouped/explicit assistant compatibility remains only for diagnostics, structured assistant error/exhaustion handling and bounded Conversation Fabric result extraction. New DOM heuristics must not reintroduce assistant-text scheduling authority.

## Same-browser Conversation Fabric

Bridge `0.8.13` / content protocol `26` uses explicit parent delegation and bounded child-result reading in ordinary tabs of the same authenticated Chrome session.

The current answer body is scoped by an assistant `data-content-search-unit-key` or `data-chatgpt-search-unit-key` ending in `:assistant`, then `data-chatgpt-selection-message-id`. This excludes surrounding rating questions and user prompts. Explicit/grouped older renderer forms remain supported when that body scope is absent.

A child result is terminal/adoptable only when the expected Conversation Fabric completion marker is present and the bounded assistant result is stable across repeated observation. The marker is stripped before the result is delivered to the parent.

Submitted-user confirmation accepts a new exact user-turn identity even when history virtualization keeps the visible user-message count constant. Delegation changes neither GitHub pacing authority nor repository execution bindings.

After service-worker/session restart, DOM/page evidence may participate in child ownership recovery only together with the exact spawn transaction/request/bootstrap/current-child-URL claim. A tab id or visually plausible child page by itself is never sufficient ownership proof.

## Assistant generation state

Generation is active when a visible ChatGPT Stop control is present:

```text
button[data-testid="stop-button"]
button[data-testid="composer-stop-button"]
```

Recovery/reload and managed diagnostic-browser stop fail closed while generation is active unless an explicit emergency force path is deliberately used.

## Conversation-length exhaustion

A conversation is exhausted only when the latest supported assistant/error turn contains all required structured evidence:

- `.text-token-text-error`;
- normalized text containing `You've reached the maximum length for this conversation`;
- a descendant button whose normalized visible text is exactly `Start new chat`.

Generated CSS classes, SVG ids, exact nesting depth and complete sentence equality are not part of the contract.

On detection Bridge records `conversation_exhausted`, disables that local conversation execution state and clears its conversation alarm. Automatic rollover is outside this contract.

## Recoverable assistant terminal errors

Recognized post-submission terminal errors are exactly:

```text
Message delivery timed out. Please try again.
Resume stream unavailable
```

A recoverable error requires structured error evidence plus ChatGPT's native Retry control. Unknown Retry-looking cards fail closed.

A matching error followed by any newer user/assistant turn is stale and must not be retried.

## Retry authorization boundary

Detection is not authorization. Automatic Retry requires worker revalidation of:

- exact preferred tab;
- exact normalized conversation URL;
- current binding revision/generation safety epoch;
- global Master enabled state;
- conversation enabled state;
- Bridge ownership of the triggering user message.

Bridge ownership is derived from the exact current chat wake envelope. Legacy binding revision may remain part of local retry epochs, but repository metadata is not execution authority. A terminal error following a normal operator-authored prompt may be diagnosed but must not be clicked automatically.

Immediately before Retry the guard rechecks the same live error snapshot, generation state and Retry-button usability. Bridge clicks ChatGPT's native Retry button and never resubmits an already-accepted prompt for these error classes.

## Retry identity and budget

Assistant DOM ids are not durable retry identity. The durable key is scoped to conversation, safety generation, error kind and deterministic triggering-user identity.

Authorized native Retry timing remains:

```text
attempt 1: 1.5 s
attempt 2: 5 s
attempt 3: 15 s
```

After the third unsuccessful Retry, Bridge records `assistant_retry_exhausted`, disables only that conversation and clears its alarm. Normal wake delivery is blocked as `assistant_recovery_pending` while a recognized current error remains unresolved.

## Conversation identity relevant to DOM

One ChatGPT conversation has one concrete Bridge chat identity. Legacy ADD/REBIND metadata may create a new local generation/compatibility epoch, but it does not authorize repository work. Wake ownership and DOM safety are scoped to the exact conversation and current delivery/safety generation.

A parent Superchat may reason across multiple donor/target repositories without making DOM identity ambiguous. Any Local Agent task still resolves its actual target through the canonical runtime catalog, requires `execution_enabled=true` and uses the exact canonical target binding.

Never infer repository execution authority from DOM ids, assistant/user text, renderer structure, Bridge binding metadata or model output.

## Intentionally unsupported assumptions

Do not depend on:

- generated/Tailwind CSS class names;
- generated SVG ids;
- exact element depth;
- any one assistant-role family existing globally;
- `data-message-id` remaining stable across rehydration;
- a role-marker node containing the corresponding message body;
- a normal page refresh reloading stale unpacked MV3 extension code;
- assistant DOM markers as the scheduling source of truth;
- a reused child tab id as ownership proof;
- speculative automatic cross-conversation rollover.

Renderer changes must be added only from bounded live evidence plus focused DOM tests and real-extension browser regression coverage.
