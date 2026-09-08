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

Autonomous planner pacing is intentionally slower than the protocol's absolute compatibility minimum. Healthy active Local Agent work should not be polled every 30 seconds: use `NEXT` no sooner than about two minutes for an early liveness check and normally 5-10 minutes for multi-minute builds/tests unless exact evidence supports a nearer completion.

## Conversation controls

A control is accepted from the end of the latest assistant message in that exact configured conversation. Text before the marker needs no separating whitespace: `Acknowledged.[LAB:PAUSE]` works. After the marker, including subsequent lines or paragraphs, only whitespace and these decorations are allowed: straight quotes/apostrophes, typographic quotes `“ ” „ ‘ ’ ‚ « » ‹ ›`, punctuation `. , ! ? ; : …`, dashes `- – —`, Markdown characters (asterisk, underscore, backtick, tilde), and closing brackets `) ] }`. Letters, numbers, emoji and other symbols after the marker cause rejection. Prefer a separate marker line:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:NEXT=2m]
[LAB:NEXT=10m]
[LAB:INTERVAL=30m]
[LAB:INTERVAL=AUTO]
```

Compatibility `LOCAL_AGENT_BRIDGE:` forms remain accepted.

Only the last candidate beginning with `[LAB:` or `[LOCAL_AGENT_BRIDGE:` is considered. A malformed or unsupported final candidate rejects the answer; the parser never falls back to an earlier command. Command spelling and duration limits remain strict.

Quotes and rendered Markdown (`code`, `pre`, `strong`, `blockquote`) do not exempt a trailing marker from execution. An example or a negated sentence ending with a marker can therefore execute it. To explain a marker without executing it, put explanatory text after it. The Bridge recognizes syntax and position, not the intent of the preceding prose.

- `STOP` disables only that conversation and clears its persistent interval override.
- `PAUSE` disables only that conversation while preserving its interval override.
- `RESUME` re-enables that conversation and schedules a near-term retry wake.
- `NEXT=<duration>` **arms or re-arms** that conversation, sets `enabled=true`, and changes only its next wake. The normal interval and global master switch are unchanged. The compatibility protocol accepts 30 seconds through 24 hours; autonomous healthy-task polling uses the stricter two-minute-or-longer planner policy above.
- `INTERVAL=<minutes>` sets the persistent per-conversation interval override.
- `INTERVAL=AUTO` returns that conversation to runtime/default pacing.

Per-conversation operator values are ordinary chat state, not a higher-priority lock. A later assistant control may therefore overwrite the chat's enabled/paused state, next wake or interval. The global **Master** switch is different: it is operator-only, assistant controls cannot modify it, and content-script messages are not authorized to call global-settings mutations.

The control fingerprint is deduplicated per conversation. Rescanning the same answer does not reapply its command. The same command in a new answer is a new control; repeated `RESUME` may reset the near-term wake time. Controls cannot change repository identity.

Transient control-delivery failures are retried for the unchanged latest assistant answer with bounded 5-30 second backoff. Bridge no longer permanently gives up after three failed scans; a page reload is not the recovery mechanism for ordinary transient worker/message failures.

## Delivery model

Bridge intentionally does **not** keep a durable ambiguous-delivery journal.

Content protocol v4 protects the important local send boundaries: exact conversation URL, operator-draft preservation, one active delivery per conversation, preflight protocol match, authorization immediately before submission, and exact DOM confirmation when available. If a reachable open tab still runs an older content protocol, the worker injects the current protocol/content scripts and probes it again instead of requiring a manual ChatGPT-tab reload.

After insertion/submission:

- confirmed DOM insertion is `sent`;
- a missing receiver before submission is treated as safely unsent/retryable;
- if Bridge inserted its wake but ChatGPT does not expose a usable Send button in the bounded window, status is `send_button_not_ready` and the exact Bridge prompt is left visible;
- if the browser cannot confirm the submitted user message in its bounded observation window, status is `delivery_unconfirmed` and any exact retained Bridge prompt is left visible instead of being erased.

A later run may reuse a non-empty composer only when the previous Bridge state is a recoverable transport state and the composer text is byte-for-byte identical to the current Bridge prompt. Any operator edit, extra whitespace or unrelated draft blocks automatic reuse. Authorization, binding, generation and exact-conversation checks are still repeated before submission.

`delivery_unconfirmed` is diagnostic only. It does **not** disable the conversation, create `pendingDelivery`, clear the schedule, block `NEXT`/`RESUME`/other controls, require a ✓/× decision, or prevent removal. The bridge may therefore send again later if confirmation was lost after a real submission; this tradeoff is deliberate so transport uncertainty cannot deadlock normal chat operation.

Only a delivery that is actively in progress is protected by an in-memory overlap guard. That guard disappears when the send finishes or the service worker restarts.

Old schema-v3 `pendingDelivery` data is discarded during normalization. Legacy `delivery_uncertain` status is migrated to the non-blocking `delivery_unconfirmed` status.

## Active Local Agent task cancellation

The executor already supports repository-scoped `cancel_task` for an exact task id. The ChatGPT planner should use it when current run/status evidence already proves that a long-running task cannot achieve the intended outcome, rather than waiting for the task timeout. See `docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/EMERGENCY_CONTROLS.md`.

This is deliberately not a direct popup button yet. The extension has no repository write credential/native executor channel, and Bridge remains transport-only. A future direct operator cancel button needs a separate trusted transport rather than silently granting the browser extension repository write authority.

## Popup

The popup deliberately keeps each conversation card small. Per chat it exposes only:

- enable/pause switch;
- wake interval override;
- `Run now`;
- `Remove`.

Binding is selected only when adding the current chat. To choose another binding in normal UI, remove the conversation and add it again. Wake interval changes auto-save. Remove is one click and uses no native confirmation dialog. Global runtime/prompt settings stay under **Advanced settings**.

The global Master switch suspends scheduled alarms without deleting per-conversation state or changing bindings. A chat may continue to update its own paused/enabled state and desired timing while Master is off; no wake alarm fires until the operator turns Master back on.

## Worker module boundaries

`service_worker.js` is composition only. Runtime responsibilities are deliberately split so no replacement god object accumulates:

- `worker_base.js` — shared protocol constants and small process-local registries;
- `worker_state.js` — serialized Chrome storage reads/writes;
- `worker_runtime.js` — runtime fetch/cache/validation;
- `worker_binding.js` — catalog binding lookup and prompt policy;
- `worker_schedule.js` — Chrome alarms and schedule reconciliation;
- `worker_transport.js` — tab discovery, content-script preflight and delivery authorization;
- `worker_controls.js` — assistant control validation and per-chat state transitions;
- `worker_delivery.js` — one feedback delivery lifecycle;
- `worker_conversations.js` — operator conversation/global-setting mutations;
- `worker_events.js` — Chrome event/message routing only.

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

After pulling an extension update, click **Reload** on the extension card. Content protocol v4 can replace an older reachable content script in already-open ChatGPT tabs on the next preflight, so a manual reload of every chat tab is no longer the normal protocol-upgrade path. If Chrome has discarded or otherwise broken a tab, reloading that tab remains a valid recovery action. Bridge 0.5 requires Chrome 120 or newer.

## Development validation

```bash
python scripts/verify.py --only bridge
npm install --no-save --package-lock=false playwright@1.57.0
npx playwright install chromium
python scripts/verify.py --profile bridge-browser
```

Browser smoke uses a disposable offline Chromium profile and the actual unpacked extension. It covers confirmed submission, composer replacement, draft preservation, SPA navigation, overlapping sends, retained/non-blocking `delivery_unconfirmed` recovery, popup behavior and service-worker restart without contacting the operator's real ChatGPT session.
