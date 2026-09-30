# Local Agent Chat Bridge

Chrome Manifest V3 extension that binds one ChatGPT conversation to Local Agent, reconciles GitHub-backed conversation pacing, submits bounded wake prompts and handles a small set of structured ChatGPT recovery states.

## Release matrix

Candidate source for Local Agent 4.19.9:

```text
Local Agent:      v4.19.9
Chat Bridge:      0.6.0
content protocol: v13
assistant guard:  v8
runtime schema:    3 + optional conversation_controls
```

Until `main` is explicitly advanced and the installed runtime is verified, the deployed Local Agent release remains v4.19.8. The live daily-Chrome candidate 0.6.0 has completed the GitHub-backed E2E described in `docs/RELEASE_NOTES_V4.19.9.md`.

Canonical behavior is defined by current source plus:

- `docs/GITHUB_BRIDGE_CONTROL.md`;
- `docs/AUTONOMOUS_CHAT_LOOP.md`;
- `docs/GOLDEN_STANDARD.md`;
- `docs/HOST_OPS_MULTIREPO.md`;
- `docs/CHATGPT_DOM_CONTRACT.md`.

Historical handoffs/release notes are evidence, not the current control contract.

## Architecture

```text
ChatGPT planner
     |
     | GitHub connector edits/reads desired state
     v
chat-bridge-state/chat_bridge/runtime.json
     |
     | public read-only fetch
     v
Chat Bridge service worker
     |
     | chrome.alarms
     v
exact ChatGPT conversation/tab
     |
     | composer + live Send control
     v
planner wake
```

For a GitHub-managed chat the DOM is **not** the source of truth for pacing/status.

## Binding model

Every configured conversation stores one current binding:

- conversation id/URL;
- repository id/name;
- canonical `agent_binding`;
- binding revision;
- local execution/cache state.

`planner_scope=repository` restricts planning to that repository. Explicit `planner_scope=multirepo` allows targets from the validated runtime catalog without changing the conversation binding. `host-ops` is the canonical multirepo operator workspace.

Every Local Agent task still carries the exact binding of its **target** repository. `local-agent` is intentionally execution-disabled and is edited through direct GitHub operations.

## GitHub-backed pacing/status

A managed conversation has one exact record in the optional top-level `conversation_controls` array in the public runtime state.

GitHub is authoritative for:

```text
STATUS
PAUSE
RESUME
NEXT
INTERVAL
```

Every schedule mutation increments `control_generation`. Status is a read. Binding/repository/revision mismatches fail closed.

The extension polls remote state with a dedicated one-minute MV3 alarm. Worker activation ensures that alarm exists, including manual extension Reload.

The extension contains no GitHub token and does not write desired state.

The global Master switch remains independent local operator state and is never changed by conversation desired state.

See `docs/GITHUB_BRIDGE_CONTROL.md` for the exact record and reconciliation semantics.

## Legacy LAB surface

LAB remains a migration/maintenance compatibility protocol. It is no longer the normal schedule transport for a GitHub-managed chat.

### Schedule markers

Legacy assistant schedule markers (`STOP`, `PAUSE`, `RESUME`, `NEXT`, `INTERVAL`) and user `OP:ENABLE` / `OP:DISABLE` / `OP:INTERVAL` return `github_control_managed` for a GitHub-owned conversation and do not mutate pacing.

### Binding migration

These remain explicit until a future GitHub binding-control design replaces them:

```text
[LAB:ADD=<repository-id>]
[LAB:REBIND=<repository-id>]
[LAB:REMOVE]
[LAB:OP:ADD=<repository-id>]
[LAB:OP:REMOVE]
```

Binding mutations validate exact runtime-catalog identity and create a fresh binding/bootstrap boundary where applicable.

### Maintenance/diagnostics

Narrow maintenance remains available:

```text
[LAB:RELOAD=CONTENT]
[LAB:RELOAD=BRIDGE]
[LAB:RESTART=WORKER]
```

Legacy inspection commands may remain useful during migration, but `STATUS` for a managed conversation is the GitHub desired-state record, not an assistant-DOM feedback round trip.

## Wake envelope

Every Bridge wake carries the immutable conversation workspace identity:

```text
[LA_AGENT=<conversation binding UUID>]
[LA_REPO=<conversation repository id>]
[LA_REPOSITORY=<owner/name>]
[LA_CHAT=<conversation id>]
```

A GitHub-managed wake also tells the planner that schedule/status controls must be performed through the exact `conversation_controls` record and that assistant LAB schedule markers are legacy no-ops.

## Wake submission

The content script owns only the browser delivery boundary:

1. exact normalized conversation URL;
2. no visible active generation Stop control;
3. composer exists and is empty, or contains the exact reusable Bridge prompt;
4. insert exact prompt;
5. authorize delivery against current worker state;
6. re-resolve the live enabled Send button immediately before submission;
7. click the live button (`requestSubmit()` is fallback only);
8. confirm the exact new user turn.

Outcomes are bounded:

- `sent` — submitted user DOM confirmed;
- `send_button_not_ready` — usable Send control not available in time;
- `delivery_unconfirmed` — submission attempt happened but exact user turn was not confirmed;
- other fail-closed lifecycle/authorization reasons.

Operator edits are never overwritten.

## DOM scope after 0.6.0

DOM compatibility remains necessary for browser facts only:

- composer and Send control;
- active-generation Stop control;
- submitted-user confirmation;
- recognized assistant terminal Retry cards;
- conversation-length exhaustion;
- explicit legacy binding/maintenance migration controls.

Assistant-turn DOM heuristics must not decide whether a GitHub-managed conversation is paused, resumed or scheduled.

See `docs/CHATGPT_DOM_CONTRACT.md`.

## Recoverable assistant errors

Recognized terminal errors remain:

```text
Message delivery timed out. Please try again.
Resume stream unavailable
```

Automatic Retry requires the exact preferred tab/conversation, current binding revision/generation, enabled state and Bridge ownership of the triggering prompt. Unknown Retry-looking cards fail closed. The durable retry budget remains three authorized Retry clicks (1.5 s, 5 s, 15 s).

## Popup

The popup remains a local operator surface for binding/onboarding, Master, manual Run now and diagnostics. For a GitHub-managed conversation, remote desired state repairs local pacing drift on the next reconcile; GitHub is authoritative for pacing.

## Installation

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Load unpacked `chat_bridge/`.
4. Open a concrete `https://chatgpt.com/c/<id>` conversation.
5. Configure its binding.
6. Add an exact `conversation_controls` record to live `chat-bridge-state` when migrating the chat to GitHub-backed pacing.
7. Reload the unpacked extension after runtime source upgrades and verify the extension version.

A normal ChatGPT page refresh is not a substitute for reloading a stale MV3 extension service worker.

## Verification

Focused Bridge verification:

```bash
python scripts/verify.py --only bridge
```

Real-extension browser verification:

```bash
python scripts/verify.py --profile bridge-browser
```

Runtime-changing releases require full CI plus macOS smoke and a bounded live desired-state E2E ending PAUSED, according to `AGENTS.md` and `docs/GOLDEN_STANDARD.md`.
