# Local Agent Chat Bridge

Chrome Manifest V3 extension that schedules bounded wake-ups for explicitly configured ChatGPT conversations. The bridge is transport and scheduling only: ChatGPT plans work and `local-agent` executes deterministic tasks when that repository is execution-enabled.

Canonical planner/executor rules live in `docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/OPERATIONS.md`.

## Identity model

Chat Bridge state schema v3 makes repository routing explicit:

```text
one ChatGPT conversation == one agent_binding UUID == one repository id == one GitHub repository
```

Each configured conversation stores its repository id, repository name, agent binding, binding revision, pacing state and independent alarm. Normal assistant conversation controls never change those binding fields. Unbound migrated conversations stay disabled with `binding_required`, and a runtime/catalog mismatch fails closed as `binding_catalog_mismatch` instead of guessing another repository.

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

## LAB command model

`control_protocol.js` owns one formal command catalog. Commands are divided by privilege instead of growing as undocumented ad-hoc markers.

Assistant-safe discovery/diagnostic commands:

```text
[LAB:HELP]
[LAB:CAPABILITIES]
[LAB:STATUS]
[LAB:DEBUG]
[LAB:SETTINGS]
[LAB:CHATS]
[LAB:CHAT=<chat-id>]
```

Bridge-local maintenance commands:

```text
[LAB:RELOAD=CONTENT]
[LAB:RELOAD=BRIDGE]
[LAB:RESTART=WORKER]
```

`RESTART=WORKER` is an alias for Bridge runtime reload because Chrome exposes extension reload rather than a standalone public API for restarting only one MV3 service worker.

Existing assistant pacing controls remain:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:NEXT=2m]
[LAB:NEXT=10m]
[LAB:INTERVAL=30m]
[LAB:INTERVAL=AUTO]
```

Operator chat mutations use a separate namespace and are processed **only from a user-authored ChatGPT message**:

```text
[LAB:OP:ADD=<repository-id>]
[LAB:OP:REMOVE]
[LAB:OP:ENABLE]
[LAB:OP:DISABLE]
[LAB:OP:INTERVAL=<minutes|AUTO>]
[LAB:OP:RELOAD=CONTENT]
[LAB:OP:RELOAD=BRIDGE]
```

The assistant parser rejects `LAB:OP:*`. The content script's operator scanner reads only the latest DOM message with `data-message-author-role="user"`; the worker additionally requires the same extension id, top frame and exact normalized conversation URL. Operator commands are persistently deduplicated in a bounded cache so ADD/REMOVE/reload operations do not replay after content/extension reload.

`OP:ADD` resolves only an exact repository id from the current runtime catalog and creates the chat disabled, matching conservative popup onboarding. It never guesses a repository. A different repository for an already-bound chat is rejected; change binding by explicit remove/add rather than implicit rebind.

## Diagnostic feedback loop

Assistant-safe inspect commands return a Bridge-generated user message beginning with:

```text
[LA_BRIDGE_FEEDBACK]
```

This feedback is local read-only evidence, not operator approval. It allows the same ChatGPT conversation to diagnose Bridge without DevTools/manual log copy.

- `HELP` returns the live command catalog and privilege classes.
- `CAPABILITIES` reports installed Bridge capabilities and explicitly unavailable authority.
- `STATUS` returns this conversation's configured/bound/schedule state.
- `DEBUG` returns extension version, expected and reported content protocol, exact tab/url, last delivery state, Master state and runtime source/pacing.
- `SETTINGS` returns effective current-chat settings. The `local-agent` infrastructure binding may also see Bridge-global settings.
- `CHATS` lists all configured chat routing metadata only from the `local-agent` infrastructure binding. Ordinary project-bound chats receive current-chat-only output.
- `CHAT=<chat-id>` may inspect another chat only from the `local-agent` infrastructure binding.

Bridge diagnostics deliberately do **not** provide direct repository task cancellation or Local Agent supervisor restart authority. `CAPABILITIES` reports those as unavailable. Existing repository-scoped `cancel_task` still belongs to the Git-backed Local Agent control plane.

## Conversation control syntax

A control is accepted from the end of the latest assistant message in that exact conversation. Text before the marker needs no separating whitespace: `Acknowledged.[LAB:PAUSE]` works. After the marker, including subsequent lines or paragraphs, only whitespace and these decorations are allowed: straight quotes/apostrophes, typographic quotes `“ ” „ ‘ ’ ‚ « » ‹ ›`, punctuation `. , ! ? ; : …`, dashes `- – —`, Markdown characters (asterisk, underscore, backtick, tilde), and closing brackets `) ] }`. Letters, numbers, emoji and other symbols after the marker cause rejection. Compatibility `LOCAL_AGENT_BRIDGE:` forms remain accepted for the assistant control namespace.

Only the last candidate beginning with `[LAB:` or `[LOCAL_AGENT_BRIDGE:` is considered. A malformed or unsupported final candidate rejects the answer; the parser never falls back to an earlier command. Quotes and rendered Markdown (`code`, `pre`, `strong`, `blockquote`) do not exempt a trailing marker from execution. Put explanatory text after examples that must not execute.

- `STOP` disables only that conversation and clears its persistent interval override.
- `PAUSE` disables only that conversation while preserving its interval override.
- `RESUME` re-enables that conversation and schedules a near-term retry wake.
- `NEXT=<duration>` arms or re-arms that conversation, sets `enabled=true`, and changes only its next wake. The compatibility protocol accepts 30 seconds through 24 hours; autonomous healthy-task polling uses the stricter two-minute-or-longer planner policy.
- `INTERVAL=<minutes>` sets the persistent per-conversation interval override.
- `INTERVAL=AUTO` returns that conversation to runtime/default pacing.

Per-conversation assistant pacing controls may overwrite ordinary chat enabled/paused state, next wake or interval. The global **Master** switch remains operator-only. No assistant-safe command can change repository binding.

Transient assistant-control failures are retried for unchanged assistant content with bounded 5-30 second backoff and no fixed terminal-attempt exhaustion.

## Delivery model

Bridge intentionally does **not** keep a durable ambiguous-delivery journal.

Content protocol v4 protects exact conversation URL, operator-draft preservation, one active delivery per conversation, authorization immediately before normal wake submission, and exact DOM confirmation when available. `CONTENT_PROTOCOL_VERSION` is owned only by `control_protocol.js`; content, worker, popup and tests consume that shared value.

Popup and scheduled-wake paths share worker-owned content activation. Popup does not maintain a second protocol version or `chrome.scripting.executeScript` implementation. When a tab must be refreshed, the worker disposes current Bridge/guard listeners, injects `control_protocol.js`, `content_retry.js`, `content.js`, `dom_contract.js` and `exhaustion_guard.js`, then probes readiness again. A reachable older content script therefore must not require a normal manual ChatGPT page reload.

After insertion/submission:

- confirmed DOM insertion is `sent`;
- a missing receiver before submission is treated as safely unsent/retryable;
- if Bridge inserted its wake but ChatGPT does not expose a usable Send button in the bounded window, status is `send_button_not_ready` and the exact Bridge prompt remains visible;
- if the browser cannot confirm the submitted user message in its bounded observation window, status is `delivery_unconfirmed` and any exact retained Bridge prompt remains visible instead of being erased.

A later run may reuse a non-empty composer only when the previous Bridge state is recoverable and the composer text is byte-for-byte identical to the current Bridge prompt. Any operator edit, extra whitespace or unrelated draft blocks automatic reuse.

`delivery_unconfirmed` is diagnostic only. It does not disable the conversation, create `pendingDelivery`, clear the schedule, block controls, require a manual resolution decision or prevent removal.

## Active Local Agent task cancellation

The executor already supports repository-scoped `cancel_task` for an exact task id. The ChatGPT planner should use it when current run/status evidence already proves that a long-running task cannot achieve the intended outcome, rather than waiting for the task timeout. See `docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/EMERGENCY_CONTROLS.md`.

This is deliberately not a direct Bridge command in 0.5.6. The extension has no repository-write credential/native executor channel. A future direct cancel command needs a separate trusted operator transport.

## Popup

The popup exposes per chat:

- enable/pause switch;
- wake interval override;
- `Run now`;
- `Remove`.

Binding can be selected when adding the current chat. The same operator actions are also available from user-authored `LAB:OP:*` commands. To choose another repository for an existing chat, remove it and add it again; no implicit assistant rebind exists.

The global Master switch suspends scheduled alarms without deleting per-conversation state or changing bindings.

## Worker module boundaries

`service_worker.js` is composition only:

- `worker_base.js` — shared protocol constants and small process-local registries;
- `worker_state.js` — serialized Chrome storage reads/writes;
- `worker_runtime.js` — runtime fetch/cache/validation;
- `worker_binding.js` — catalog binding lookup and prompt policy;
- `worker_schedule.js` — Chrome alarms and schedule reconciliation;
- `worker_transport.js` — tab discovery, content preflight and delivery authorization;
- `worker_controls.js` — assistant scheduling/maintenance control validation;
- `worker_delivery.js` — one normal feedback delivery lifecycle;
- `worker_conversations.js` — popup/operator conversation/global-setting mutations;
- `worker_lab_commands.js` — LAB diagnostics, command feedback, operator command dedupe/mutations and force content refresh;
- `worker_events.js` — Chrome event/message routing only.

## Runtime catalog

Remote runtime schema v3 publishes pacing and the canonical agent catalog. Repository ids, repository names and binding UUIDs must each be unique. Binding UUIDs use canonical lowercase UUID text. Only runtime schema v3 is accepted and `execution_enabled` must be a JSON boolean. Invalid/unavailable runtime configuration blocks sending as `runtime_unavailable`; there is no guessed fallback identity catalog.

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
5. Open the extension, select the exact repository binding and click **Add current chat**, or type an explicit user operator command such as `[LAB:OP:ADD=local-agent]`.
6. Use a chat control or `Run now` for an end-to-end test.

After pulling an extension update, click **Reload** on the extension card. Do not normally reload every open ChatGPT tab: worker-owned content refresh is expected to replace a reachable older protocol automatically. Reload the page only when Chrome has discarded/broken the tab or explicit diagnostics show content cannot be activated. Bridge 0.5.6 requires Chrome 120 or newer.

## Development validation

```bash
python scripts/verify.py --only bridge
npm install --no-save --package-lock=false playwright@1.57.0
npx playwright install chromium
python scripts/verify.py --profile bridge-browser
```

Browser smoke uses a disposable offline Chromium profile and the actual unpacked extension. It covers confirmed submission, composer replacement, draft preservation, SPA navigation, overlapping sends, retained/non-blocking `delivery_unconfirmed` recovery, popup behavior, service-worker restart and protocol-refresh regressions without contacting the operator's real ChatGPT session.
