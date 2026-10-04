# Local Agent Chat Bridge

Chrome Manifest V3 extension for managed ChatGPT conversation transport, GitHub-backed conversation pacing and browser-native Conversation Fabric reasoning delegation.

## Current contract

```text
Local Agent release line: 4.20.6
Chat Bridge:             0.8.3
content protocol:        18
assistant guard:         8
runtime schema:          3 + optional conversation_controls
```

Chat Bridge is a transport/scheduling component. It does **not** grant repository execution authority.

Canonical current behavior is defined by source plus:

- `AGENTS.md`;
- `docs/GOLDEN_STANDARD.md`;
- `docs/AUTONOMOUS_CHAT_LOOP.md`;
- `docs/GITHUB_BRIDGE_CONTROL.md`;
- `docs/HOST_OPS_MULTIREPO.md`;
- `docs/CHATGPT_DOM_CONTRACT.md`.

Historical handoffs/release notes are evidence only.

## Architecture

```text
GitHub conversation desired state
          |
          v
Chat Bridge MV3 service worker
          |
          +--> exact managed parent tab / bounded wake delivery
          |
          +--> LOCAL_AGENT_CF campaign
                    |
                    +--> ordinary child tabs in the same authenticated Chrome session
                    +--> stable result observation
                    +--> durable campaign/result state
                    +--> exact owned-tab cleanup
                    +--> terminal feedback at most once
```

The ChatGPT DOM is not the scheduling source of truth for a GitHub-managed chat.

## Transport vs execution authority

Every configured conversation stores a concrete conversation id/URL plus local transport/safety state. Legacy repository/binding fields may remain in migrated state for compatibility, but they do not authorize repository work.

Repository reasoning scope comes from the active goal or durable request and may span donor and target repositories without chat rebind.

For any executable Local Agent task, the parent must resolve the **actual target repository** through the canonical runtime catalog, require `execution_enabled=true`, and use that target's exact canonical `agent_binding`. Registry/control agreement without a matching catalog record fails closed.

The current canonical catalog enables `local-agent`. This is not a transport exception or bypass: self-execution follows the same catalog, binding, lease, resource and emergency-control gates as every other execution-enabled target.

## GitHub-backed pacing/status

A managed conversation has one exact optional `conversation_controls` record in public runtime state.

GitHub is authoritative for:

```text
STATUS
PAUSE
RESUME
NEXT
INTERVAL
```

Every schedule mutation increments `control_generation`. Status is a read. The global Bridge Master switch is independent local operator state and is never changed by per-conversation desired state.

The extension polls remote state with a dedicated one-minute MV3 alarm. Worker activation ensures that alarm exists, including after extension/service-worker reload. The extension contains no GitHub token and does not write GitHub desired state.

See `docs/GITHUB_BRIDGE_CONTROL.md`.

## Wake submission

The content/worker path owns only the browser delivery boundary:

1. exact normalized conversation URL;
2. no visible active generation Stop control;
3. composer exists and is empty, or contains the exact reusable Bridge prompt;
4. insert exact prompt;
5. authorize delivery against current worker state;
6. re-resolve the live enabled Send control immediately before submission;
7. submit;
8. confirm the exact new user turn.

Operator edits are never overwritten. Ordinary ambiguous/unconfirmed wake delivery is diagnostic and is not automatically replayed.

## Browser-native Conversation Fabric

A managed parent delegates bounded reasoning with one plain-text control block:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"delegate","children":[{"id":"analysis","role":"research","prompt":"Analyze the supplied source context."},{"id":"check","role":"verification","prompt":"Independently verify the supplied claim."}]}
LOCAL_AGENT_CF>>>
```

Supported child roles are `research`, `implementation`, `verification` and `integration`. Every child remains reasoning-only. Children do not inherit parent context, create `.agent/tasks`, run machine commands, mutate repositories or make the final parent decision.

Production children are ordinary tabs in the operator's already authenticated primary Chrome session. No second production Chrome/profile, CDP control plane, cookie copy or separate ChatGPT login is part of normal delegation.

### Durable campaign lifecycle

- Campaign identity and captured results are stored in `chrome.storage.local`.
- Stable child results require the explicit completion marker and repeated identical observation.
- Each stable result is persisted before sibling completion or tab cleanup.
- Transient observation failures remain pending/recoverable.
- After service-worker/session restart, an existing child may be reattached only if the page proves the exact transaction id, child-request digest, bootstrap digest and current child conversation URL. Tab id alone never proves ownership.
- Ambiguous/pre-submit spawning fails closed; Bridge does not blindly replay an already-submitted bootstrap.
- Completed/failed cleanup closes only exact owned child tabs.

### Collection

Normal campaign observation is worker-driven. The existing one-minute GitHub-control alarm reconciles conversation controls and then polls active Fabric campaigns while parent + Master are enabled.

An explicit `collect` control is a bounded recovery/inspection operation for already-submitted children. It must never resubmit their prompts.

### Terminal feedback

Terminal parent feedback has durable at-most-once semantics:

- a campaign-specific delivery claim is persisted before crossing the Send boundary;
- definite no-send clears the claim;
- confirmed delivery marks feedback delivered;
- an ambiguous claim surviving worker restart is treated as consumed and is not resent.

This intentionally prefers a potentially missed terminal notification after an ambiguous crash over duplicate terminal feedback.

A parent cannot start a different new delegation while an older terminal campaign still has undelivered feedback. This prevents stale cross-campaign replay.

## Legacy LAB compatibility

LAB scheduling/binding controls remain migration/maintenance compatibility only. They are not the normal pacing mechanism for GitHub-managed chats and must not be used to switch executable target authority.

Maintenance commands may still exist for bounded diagnostics, but normal Superchat work uses GitHub `conversation_controls` plus `LOCAL_AGENT_CF` for child reasoning.

## Direct GitHub edits vs Local Agent

Use direct GitHub edits when an exact repository/source/docs diff plus CI is sufficient. Use Local Agent only for work that genuinely requires local commands, builds/tests, devices, services or host state. Conversation Fabric children perform neither mutation path; the parent owns edits, executable-task publication, CI, merge and final verdict.

## Installation

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Load unpacked `chat_bridge/`.
4. Open the concrete managed `https://chatgpt.com/c/<id>` conversation.
5. Add/manage the conversation in the popup.
6. Configure matching `conversation_controls` in live `chat-bridge-state` when GitHub-backed pacing is used.
7. Reload the unpacked extension after runtime source upgrades and verify the installed version.

A normal ChatGPT page refresh is not a substitute for reloading stale extension code.

## Verification

Focused Bridge verification:

```bash
python scripts/verify.py --only bridge
```

Real-extension browser verification:

```bash
python scripts/verify.py --profile bridge-browser
```

Important Fabric regressions include:

```bash
node chat_bridge/conversation_fabric_protocol.test.js
node chat_bridge/conversation_fabric_worker.test.js
node scripts/conversation_fabric_dom_smoke.cjs
node scripts/conversation_fabric_browser_smoke.cjs
```

Runtime-changing releases require full exact-head CI, macOS smoke and bounded real-browser/live acceptance for changed lifecycle semantics.

`conversation_live_slice_browser.cjs` and isolated-profile tooling are legacy development/test evidence, not the production Superchat delegation backend.
