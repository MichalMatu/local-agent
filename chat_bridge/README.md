# Local Agent Chat Bridge

Chrome Manifest V3 extension that schedules bounded autonomous wake-ups for multiple explicitly configured ChatGPT conversations. The bridge remains transport only: ChatGPT plans work and `local-agent` executes deterministic tasks.

The canonical planner/executor contract is documented in `docs/AUTONOMOUS_CHAT_LOOP.md`, `docs/OPERATIONS.md` and `docs/MULTI_REPOSITORY.md`.

## v0.3 model

Chat Bridge v0.3 replaces the old single-conversation state with schema v2:

- multiple conversations can be enabled at the same time;
- every conversation has an independent alarm, status, interval override and assistant-control dedupe state;
- `STOP`, `PAUSE`, `RESUME`, `INTERVAL` and `NEXT` affect only the conversation that emitted the marker;
- a global master switch can suspend scheduling without deleting per-conversation state;
- each conversation can store an automatically detected label and optional Local Agent `repositoryId` routing hint;
- the previous v0.2 storage layout is migrated automatically on first startup.

Chrome must remain running and each scheduled conversation must remain open in a tab. The tab does not need to be foregrounded.

## Token-efficient wake flow

New or migrated conversations receive one bootstrap prompt. After the bootstrap is sent successfully, ordinary wake-ups use a compact wake prompt instead of repeating the full Local Agent policy every time.

The default compact prompt is intentionally short:

```text
[LA_WAKE] Continue the active Local Agent goal from exact target-repo evidence. Do not recap unchanged state; keep this wake terse.
```

Runtime schema v2 separates the two prompt types:

```json
{
  "schema_version": 2,
  "interval_minutes": 10,
  "busy_retry_minutes": 1,
  "bootstrap_prompt": "...",
  "wake_prompt": "..."
}
```

Schema v1 runtime files remain accepted for compatibility. Their legacy `prompt` is treated as the one-time bootstrap prompt, while compact wake text comes from local settings.

The service worker keeps a short in-memory runtime-config cache so simultaneous conversations do not refetch the same remote runtime file unnecessarily.

## Conversation-scoped control protocol

A bridge command is accepted only when it is the final non-empty line of the latest assistant message in that exact configured conversation.

Preferred compact markers:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:NEXT=30s]
[LAB:NEXT=10m]
[LAB:INTERVAL=30m]
[LAB:INTERVAL=AUTO]
```

Legacy markers remain valid:

```text
[LOCAL_AGENT_BRIDGE:STOP]
[LOCAL_AGENT_BRIDGE:PAUSE]
[LOCAL_AGENT_BRIDGE:RESUME]
[LOCAL_AGENT_BRIDGE:NEXT=30s]
[LOCAL_AGENT_BRIDGE:INTERVAL=30]
[LOCAL_AGENT_BRIDGE:INTERVAL=AUTO]
```

Semantics:

- `STOP` disables only that conversation and clears its persistent interval override.
- `PAUSE` disables only that conversation while preserving its interval override.
- `RESUME` re-enables that conversation and schedules a near-term busy-retry wake.
- `NEXT=<duration>` schedules only the next wake and does not change the normal interval. Durations are bounded to 30 seconds through 24 hours.
- `INTERVAL=<minutes>` sets that conversation's persistent interval override.
- `INTERVAL=AUTO` removes the override and returns to runtime/default pacing.

Control dedupe is stored per conversation. The content script includes the latest assistant-message identity in the fingerprint so a later identical response is not mistaken for an already processed command.

## Popup configuration

The extension popup provides:

- a global master scheduler switch;
- one-click **Add current chat** for the active ChatGPT conversation;
- automatic conversation id/URL extraction, including project-scoped ChatGPT conversation URLs;
- automatic initial label from the browser tab title;
- one card per configured conversation with editable label, optional repository id, enable/pause, manual interval override, `Run now`, save and remove actions;
- per-conversation last status, next wake and bootstrap/compact-wake mode;
- global runtime URL, default interval, busy retry, compact wake prompt and bootstrap prompt.

The repository id cannot be derived reliably from a ChatGPT conversation URL, so it is intentionally optional. Changing it later marks that conversation's bootstrap as pending so the new routing hint is delivered once before compact wake mode resumes.

## Install from the local-agent checkout

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the repository's `chat_bridge` directory.
4. Open a concrete ChatGPT conversation. Standard `/c/<id>` links and project-scoped links ending in `/c/<id>` are supported.
5. Open the extension and click **Add current chat**. The conversation id/URL and label are detected automatically.
6. Repeat for other conversations.
7. Edit the optional repository id only when a planner routing hint is useful.
8. Use **Run now** on a conversation card for an end-to-end test.

After updating an already loaded unpacked extension, click **Reload** on its `chrome://extensions` card. Existing v0.2 configuration is migrated automatically.

## Development validation

```bash
node --check chat_bridge/control_protocol.js
node --check chat_bridge/bridge_state.js
node --check chat_bridge/control_protocol.test.js
node --check chat_bridge/bridge_state.test.js
node --check chat_bridge/service_worker.js
node --check chat_bridge/service_worker.test.js
node --check chat_bridge/content.js
node --check chat_bridge/popup.js
node chat_bridge/control_protocol.test.js
node chat_bridge/bridge_state.test.js
node chat_bridge/service_worker.test.js
python -m json.tool chat_bridge/manifest.json >/dev/null
python -m json.tool chat_bridge/runtime.example.json >/dev/null
```
