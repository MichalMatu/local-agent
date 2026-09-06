# Local Agent Chat Bridge

Chrome Manifest V3 extension that schedules bounded wake-ups for explicitly configured ChatGPT conversations. The bridge is transport and scheduling only: ChatGPT plans work and `local-agent` executes deterministic tasks when that repository is execution-enabled.

Canonical planner/executor rules live in `docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/OPERATIONS.md`.

## Identity model

Chat Bridge state schema v3 makes repository routing explicit:

```text
one ChatGPT conversation == one agent_binding UUID == one repository id == one GitHub repository
```

Each configured conversation stores its repository id, repository name, agent binding, binding revision, pacing state and independent alarm. Normal conversation controls never change those binding fields. Unbound migrated conversations stay disabled with `binding_required`, and a runtime/catalog mismatch fails closed as `binding_catalog_mismatch` instead of guessing another repository.

The `local-agent` catalog entry is intentionally `execution_enabled: false`. It is valid for Bridge/operator infrastructure conversations but must not create Local Agent project task files.

## Wake flow

Every bootstrap and compact wake carries the exact stored identity:

```text
[LA_AGENT=<canonical UUID>]
[LA_REPO=<repository id>]
[LA_REPOSITORY=<owner/name>]
[LA_CHAT=<conversation id>]
```

The first actual wake for a newly added conversation is a bootstrap. Later wakes use the compact wake prompt. Chrome must remain running and the configured ChatGPT conversation must remain open in a tab; it does not have to be foregrounded.

Adding a conversation captures the current latest assistant-message identity as `assistantBaseline`. That existing answer is ignored as a control source. New assistant answers written after the chat is added may use the complete conversation control protocol immediately, even while the first bootstrap is still pending. A later binding revision remains protected until its fresh bootstrap establishes the new baseline.

## Conversation controls

A control is accepted only from the final non-empty line of the latest assistant message in that exact configured conversation.

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:NEXT=30s]
[LAB:NEXT=10m]
[LAB:INTERVAL=30m]
[LAB:INTERVAL=AUTO]
```

Compatibility `LOCAL_AGENT_BRIDGE:` forms remain accepted.

- `STOP` disables only that conversation and clears its persistent interval override.
- `PAUSE` disables only that conversation while preserving its interval override.
- `RESUME` re-enables that conversation and schedules a near-term retry wake.
- `NEXT=<duration>` **arms or re-arms** that conversation, sets `enabled=true`, and changes only its next wake. The normal interval and global master switch are unchanged. Durations are bounded to 30 seconds through 24 hours.
- `INTERVAL=<minutes>` sets the persistent per-conversation interval override.
- `INTERVAL=AUTO` returns that conversation to runtime/default pacing.

The control fingerprint is deduplicated per conversation. Controls cannot change repository identity.

## Delivery model

Bridge intentionally does **not** keep a durable ambiguous-delivery journal.

The content script still protects the important local send boundaries: exact conversation URL, empty/unchanged composer, one active delivery per conversation, preflight protocol match, authorization immediately before submission, and exact DOM confirmation when available.

After submission:

- confirmed DOM insertion is `sent`;
- a missing receiver before submission is treated as safely unsent/retryable;
- if the browser cannot confirm the submitted user message in its short observation window, the status is `delivery_unconfirmed`.

`delivery_unconfirmed` is diagnostic only. It does **not** disable the conversation, create `pendingDelivery`, clear the schedule, block `NEXT`/`RESUME`/other controls, require a ✓/× decision, or prevent removal. The bridge may therefore send again later if confirmation was lost after a real submission; this tradeoff is deliberate so transport uncertainty cannot deadlock normal chat operation.

Only a delivery that is actively in progress is protected by an in-memory overlap guard. That guard disappears when the send finishes or the service worker restarts.

Old schema-v3 `pendingDelivery` data is discarded during normalization. Legacy `delivery_uncertain` status is migrated to the non-blocking `delivery_unconfirmed` status.

## Popup

The popup deliberately keeps each conversation card small. Per chat it exposes only:

- enable/pause switch;
- wake interval override;
- `Run now`;
- `Remove`.

Binding is selected only when adding the current chat. To choose another binding in normal UI, remove the conversation and add it again. Wake interval changes auto-save. Remove is one click and uses no native confirmation dialog. Global runtime/prompt settings stay under **Advanced settings**.

The global Master switch suspends scheduled alarms without deleting per-conversation state or changing bindings.

## Runtime catalog

Remote runtime schema v3 publishes pacing and the canonical agent catalog:

```json
{
  "schema_version": 3,
  "interval_minutes": 10,
  "busy_retry_minutes": 1,
  "bootstrap_prompt": "...",
  "wake_prompt": "...",
  "agents": [
    {
      "repository_id": "matrixhub",
      "repository": "MichalMatu/MatrixHub",
      "agent_binding": "033327ab-700d-43b4-9b3b-caff1acaa2c7",
      "execution_enabled": true
    }
  ]
}
```

Repository ids, repository names and binding UUIDs must each be unique. Binding UUIDs use canonical lowercase UUID text. Only runtime schema v3 is accepted and `execution_enabled` must be a JSON boolean. Invalid/unavailable runtime configuration blocks sending as `runtime_unavailable`; there is no guessed fallback identity catalog.

## Executor-side protection

Bridge routing is only one boundary. For executable repositories Local Agent independently requires:

```text
local repository registry agent_binding
    == <control checkout>/.agent/binding.json agent_binding
    == task.agent_binding
```

The parallel worker and serial fallback enforce the same contract before task execution. The global Local Agent `disabled` marker remains higher priority than repository admission.

## Install/update

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select this repository's `chat_bridge` directory.
4. Open a concrete ChatGPT conversation.
5. Open the extension, select the exact repository binding and click **Add current chat**.
6. Repeat for other conversations.
7. Use a chat control or `Run now` for an end-to-end test.

After pulling an update, click **Reload** on the extension card and reload open ChatGPT tabs once so worker/content protocol versions match. Bridge 0.5 requires Chrome 120 or newer.

## Development validation

```bash
python scripts/verify.py --only bridge
npm install --no-save --package-lock=false playwright@1.57.0
npx playwright install chromium
python scripts/verify.py --profile bridge-browser
```

Browser smoke uses a disposable offline Chromium profile and the actual unpacked extension. It covers confirmed submission, composer replacement, draft preservation, SPA navigation, overlapping sends, non-blocking `delivery_unconfirmed`, popup behavior and service-worker restart without contacting the operator's real ChatGPT session.
