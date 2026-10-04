# Local Agent Chat Bridge

Chrome Manifest V3 extension that binds one ChatGPT conversation to Local Agent, reconciles GitHub-backed conversation pacing, submits bounded wake prompts and handles a small set of structured ChatGPT recovery states.

## Release matrix

Release checkpoint:

```text
Local Agent:      v4.20.6
Chat Bridge:      0.8.3 candidate
content protocol: v18
assistant guard:  v8
runtime schema:    3 + optional conversation_controls
```

The Bridge candidate adds native same-browser Superchat delegation. It does not change the Local Agent release version or repository execution authority. Candidate changes remain local until an explicit release decision.

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

## Transport and repository model

Every configured conversation stores one concrete conversation id/URL plus local transport/safety state. Legacy repository/binding fields may remain in migrated state for compatibility, but they do not authorize repository work.

Normal onboarding is repository-agnostic: open the exact ChatGPT conversation and use **Add current chat**. Repository reasoning scope comes from the active goal or durable request and may span donor/target repositories without Rebind.

Every Local Agent task still carries the exact binding of its **actual target** repository. `local-agent` is intentionally execution-disabled and is edited through direct GitHub operations.

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

Every schedule mutation increments `control_generation`. Status is a read. Schedule ownership is keyed by exact chat identity; legacy binding/repository/revision fields are not schedule authority.

The extension polls remote state with a dedicated one-minute MV3 alarm. Worker activation ensures that alarm exists, including manual extension Reload.

The extension contains no GitHub token and does not write desired state.

The global Master switch remains independent local operator state and is never changed by conversation desired state.

See `docs/GITHUB_BRIDGE_CONTROL.md` for the exact record and reconciliation semantics.

## Legacy LAB surface

LAB remains a migration/maintenance compatibility protocol. It is no longer the normal schedule transport for a GitHub-managed chat.

### Schedule markers

Legacy assistant schedule markers (`STOP`, `PAUSE`, `RESUME`, `NEXT`, `INTERVAL`) and user `OP:ENABLE` / `OP:DISABLE` / `OP:INTERVAL` return `github_control_managed` for a GitHub-owned conversation and do not mutate pacing.

### Legacy binding migration compatibility

The parser still recognizes `ADD`/`REBIND`/operator binding commands for old profiles and explicit migration diagnostics. They are not part of normal Superchat repository routing and must not be required to move between donor/target repositories. `REMOVE` remains an explicit conversation-removal control.

### Maintenance/diagnostics

Narrow maintenance remains available:

```text
[LAB:RELOAD=CONTENT]
[LAB:RELOAD=BRIDGE]
[LAB:RESTART=WORKER]
```

Legacy inspection commands may remain useful during migration, but `STATUS` for a managed conversation is the GitHub desired-state record, not an assistant-DOM feedback round trip.

## Wake envelope

Every normal Bridge wake carries the stable conversation identity plus the runtime prompt:

```text
[LA_CHAT=<conversation id>]
```

Repository catalog/binding metadata is not injected as execution authority. GitHub-managed pacing remains owned by the exact `conversation_controls` record.

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

## Same-browser Superchat delegation

Candidate Bridge version: **0.8.3**, content protocol **18**. The Local Agent release remains 4.20.6.

Reload the already-installed unpacked extension after updating its checkout. Add the parent conversation through the popup and enable that conversation with Master on. Existing configured tabs are refreshed through the shared Bridge content lifecycle. No CDP endpoint, profile copy, or additional Chrome process is required.

Bootstrap and wake messages explain the native delegation contract. The parent ends an assistant response with a plain-text control block (without Markdown fences or trailing prose):

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"delegate","children":[{"id":"analysis","role":"research","prompt":"Analyze the supplied source context."},{"id":"check","role":"verification","prompt":"Independently verify the supplied claim."}]}
LOCAL_AGENT_CF>>>
```

Each child receives its own bounded prompt and reasoning-only instructions. Child prompts must contain their source context; the children do not inherit the parent's conversation. Supported roles are research, implementation, verification, and integration; every role remains reasoning-only.

The existing minute GitHub-control poll collects stable child answers and delivers the results through the normal authorized feedback path. The parent synthesizes those results. A campaign holds at most four child slots globally and one active delegation per parent. Disable the parent or Master to stop further collection/delivery.

Campaigns and captured results survive worker/browser restart in local extension storage. Interrupted spawning fails explicitly without replaying a bootstrap. Results are saved before tabs close, and cleanup checks the exact spawn ownership claim. Campaigns time out after 15 minutes while enabled. Extension reload may clear session tab claims. Bridge recovers ownership only after the child controller validates the exact transaction, request digest, bootstrap digest, and current child URL. Missing or conflicting page claims fail closed; a reused tab id alone never proves ownership. An explicit collect can recover already-submitted children after an observation failure without resubmitting their prompts. Completed history is bounded; undelivered evidence is retained.

Focused checks:

```bash
node chat_bridge/conversation_fabric_protocol.test.js
node chat_bridge/conversation_fabric_worker.test.js
node scripts/conversation_fabric_dom_smoke.cjs
node scripts/conversation_fabric_browser_smoke.cjs
python scripts/verify.py
python scripts/verify.py --profile bridge-browser
python scripts/verify.py --profile macos-smoke
```

The browser tests use offline disposable Chromium profiles. `conversation_live_slice_browser.cjs` is legacy DEV proof tooling, not the native Superchat delegation backend.
