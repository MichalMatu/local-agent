# Local Agent Chat Bridge

Chrome Manifest V3 extension that periodically sends one bounded feedback prompt to one explicitly selected ChatGPT conversation. It is intentionally separate from the deterministic local-agent execution path.

## Safety model

- Disabled by default.
- Bound to one exact ChatGPT conversation URL.
- Never sends while ChatGPT exposes a generating/stop control.
- Never overwrites non-empty composer text.
- Retries busy or temporarily unavailable pages with a bounded interval.
- Runtime prompt and timing are loaded independently from extension code.
- A local master switch remains authoritative even when remote runtime configuration changes.

## Runtime state

The default runtime configuration URL is:

```text
https://raw.githubusercontent.com/MichalMatu/local-agent/chat-bridge-state/chat_bridge/runtime.json
```

The dedicated `chat-bridge-state` branch is runtime state, not release code. The extension fetches it with `cache: no-store` before each feedback attempt. If the fetch fails or is invalid, the extension uses the locally stored fallback values.

Runtime schema:

```json
{
  "schema_version": 1,
  "interval_minutes": 10,
  "busy_retry_minutes": 1,
  "prompt": "..."
}
```

`interval_minutes` is bounded to 1..1440 and `busy_retry_minutes` to 1..60. Prompt length is bounded to 8000 characters.

## Install from the local-agent checkout

1. Let local-agent self-update to a revision containing `chat_bridge/`.
2. Open `chrome://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked** and select the repository's `chat_bridge` directory.
5. Open the ChatGPT conversation that will coordinate local-agent work.
6. Open the extension, click **Use current**, enable automatic feedback, and click **Save**.
7. Click **Run now** once as an end-to-end test.

Chrome must remain running and the selected conversation must remain open in a tab. The tab does not need to be foregrounded.

## Development validation

```bash
node --check chat_bridge/service_worker.js
node --check chat_bridge/content.js
node --check chat_bridge/popup.js
python -m json.tool chat_bridge/manifest.json >/dev/null
python -m json.tool chat_bridge/runtime.example.json >/dev/null
```
