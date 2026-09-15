# Local Agent Chat Bridge

Chrome Manifest V3 extension that schedules bounded wake-ups for explicitly configured ChatGPT conversations and can receive bounded local task-result wake hints from Local Agent. The bridge is transport and scheduling only: ChatGPT plans work and `local-agent` executes deterministic tasks when that repository is execution-enabled.

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

For a Local Agent task, the normal autonomous continuation control is now:

```text
[LAB:WAIT_TASK=<exact-task-id>]
```

`WAIT_TASK` persists one exact watch scoped to repository id, repository name, `agent_binding` and task id. Local Agent records `task_result_ready` only after the authoritative terminal result has been pushed successfully. A read-only Native Messaging host relays that bounded metadata to the extension; Bridge then wakes only the owning exact conversation.

A result-ready wake contains:

```text
[LA_EVENT=task_result_ready]
[LA_TASK=<task-id>]
```

This is only a **wake hint**. The planner must still read the exact `.agent/results/<task-id>.json` result before deciding whether the task succeeded, failed, was rejected or was cancelled.

Scheduled alarms are retained as reconciliation fallback. Native Messaging absence, restart or disconnect must never make normal scheduled continuation impossible. `NEXT` remains available for genuinely time-based rechecks but is no longer the normal way to discover completion of a healthy watched Local Agent task.

## Event-wake durability and lifecycle

The event path deliberately has two durable layers:

- Local Agent keeps a bounded event outbox under its application-support state directory until the host receives a valid ACK;
- Chat Bridge keeps bounded recent-event, exact-watch and pending-wake state in `chrome.storage.local`.

This closes the fast-task race where terminal publication happens before the assistant's `WAIT_TASK` marker is observed. When the watch is registered, Bridge checks its recent event cache immediately.

The Native Messaging connection is on-demand. It is wanted only while at least one exact watch belongs to a bound, enabled conversation and the global Master switch is on. `PAUSE`, operator disable and Master-off retain the watch but suspend the native process; resume/re-enable/Master-on reconnects and can replay the durable outbox. `STOP`, removal and rebind clear the old watch.

A transient delivery failure does not consume a pending event. Missing tab, busy/send-button conditions or an unconfirmed attempt retain the pending event until an actual delivery returns `ok`, while the normal retry/reconciliation schedule remains available.

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

Assistant pacing/continuation controls include:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:WAIT_TASK=<task-id>]
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

The assistant parser rejects `LAB:OP:*`. The content script's operator scanner reads only the latest DOM message with `data-message-author-role="user"`; the worker additionally requires the same extension id, top frame and exact normalized conversation URL. Operator commands are persistently deduplicated in a bounded cache after execution. Separately, the latest user message already present when the current content script activates is baseline-only and is not executed as a new operator command; the baseline is reset on SPA conversation changes. This prevents a historical `LAB:OP:*` marker from replaying merely because Bridge was installed, reloaded, reinjected or navigated to another chat.

`OP:ADD` resolves only an exact repository id from the current runtime catalog and creates the chat disabled, matching conservative popup onboarding. It never guesses a repository. A different repository for an already-bound chat is rejected; change binding by explicit remove/add rather than implicit rebind.

## Diagnostic feedback loop

Assistant-safe inspect commands return a Bridge-generated user message beginning with:

```text
[LA_BRIDGE_FEEDBACK]
```

This feedback is local read-only evidence, not operator approval. It allows the same ChatGPT conversation to diagnose Bridge without DevTools/manual log copy.

- `HELP` returns the live command catalog and privilege classes.
- `CAPABILITIES` reports installed Bridge capabilities, event-wake support and explicitly unavailable authority.
- `STATUS` returns this conversation's configured/bound/schedule state plus bounded event-wake state.
- `DEBUG` returns extension/content protocol information, exact tab/url, Master/runtime data and bounded event-wake diagnostics.
- `SETTINGS` returns effective current-chat settings. The `local-agent` infrastructure binding may also see Bridge-global settings.
- `CHATS` lists all configured chat routing metadata only from the `local-agent` infrastructure binding. Ordinary project-bound chats receive current-chat-only output.
- `CHAT=<chat-id>` may inspect another chat only from the `local-agent` infrastructure binding.

Event diagnostics expose transport state, protocol version, current exact task watch, pending wake, bounded recent-event count and last accepted/delivered event ids/timestamps. They do not expose task command output or add executor authority.

Bridge diagnostics deliberately do **not** provide direct repository task cancellation, arbitrary terminal access, daemon log streaming or Local Agent supervisor restart authority. Existing repository-scoped `cancel_task` still belongs to the Git-backed Local Agent control plane.

## Conversation control syntax

A control is accepted from the end of the latest assistant message in that exact conversation. Text before the marker needs no separating whitespace: `Acknowledged.[LAB:PAUSE]` works. After the marker, including subsequent lines or paragraphs, only whitespace and the documented decorations are allowed. Letters, numbers, emoji and other unsupported symbols after the marker cause rejection. Compatibility `LOCAL_AGENT_BRIDGE:` forms remain accepted for the assistant control namespace.

Only the last candidate beginning with `[LAB:` or `[LOCAL_AGENT_BRIDGE:` is considered. A malformed or unsupported final candidate rejects the answer; the parser never falls back to an earlier command. Quotes and rendered Markdown do not exempt a trailing marker from execution. Put explanatory text after examples that must not execute.

- `STOP` disables only that conversation, clears its persistent interval override and clears its exact task watch/pending wake.
- `PAUSE` disables only that conversation while preserving its interval override and exact task watch; Native Messaging is suspended while paused.
- `RESUME` re-enables the conversation and reconciles a retained pending event or reconnects Native Messaging for a retained watch.
- `WAIT_TASK=<task-id>` arms one exact task watch and retains the normal bounded alarm fallback.
- `NEXT=<duration>` arms/re-arms a one-shot time-based wake. The compatibility protocol accepts 30 seconds through 24 hours, but it is not the normal healthy-task completion mechanism.
- `INTERVAL=<minutes>` sets the persistent per-conversation interval override.
- `INTERVAL=AUTO` returns that conversation to runtime/default pacing.

Only one configured conversation may own the same exact repository/binding/task watch tuple. A conflicting second watch is rejected and that conversation keeps normal alarm fallback rather than depending on an event it does not own.

Per-conversation assistant pacing controls may overwrite ordinary chat enabled/paused state, next wake or interval. The global **Master** switch remains operator-only. No assistant-safe command can change repository binding.

Transient assistant-control failures are retried for unchanged assistant content with bounded backoff and no fixed terminal-attempt exhaustion.

## Native Messaging security model

The new native channel is intentionally narrow:

- the extension manifest requests `nativeMessaging`;
- the macOS host manifest allows exactly one installed Chrome extension origin;
- the host validates its caller origin and protocol version;
- messages are bounded length-prefixed JSON;
- extension -> host actions are handshake and ACK only;
- host -> extension data is bounded result-ready metadata only;
- no shell, terminal, task creation/cancel, arbitrary filesystem read or log-stream command exists in the protocol.

A malformed/tampered outbox event is rejected/pruned before replay. Event identity is checked against repository/binding/task/digest identity. The extension independently re-validates event schema and exact routing before state mutation.

See `docs/SECURITY_MODEL.md` and `docs/chat_bridge/EVENT_WAKE_ARCHITECTURE.md`.

## Delivery model

Bridge intentionally does **not** keep a durable ambiguous-delivery journal for ordinary wake submission uncertainty.

The shared content protocol protects exact conversation URL, operator-draft preservation, one active delivery per conversation, authorization immediately before normal wake submission, exact DOM confirmation when available and the LAB operator-control baseline. `CONTENT_PROTOCOL_VERSION` is owned only by `control_protocol.js`; content, worker, popup and tests consume that shared value.

Popup and scheduled-wake paths share worker-owned content activation. Popup does not maintain a second protocol version or `chrome.scripting.executeScript` implementation. When a tab must be refreshed, the worker disposes current Bridge/guard listeners, injects `control_protocol.js`, `content_retry.js`, `content.js`, `dom_contract.js` and `exhaustion_guard.js`, then probes readiness again. A reachable older content script therefore must not require a normal manual ChatGPT page reload.

After insertion/submission:

- confirmed DOM insertion is `sent`;
- a missing receiver before submission is treated as safely unsent/retryable;
- if Bridge inserted its wake but ChatGPT does not expose a usable Send button in the bounded window, status is `send_button_not_ready` and the exact Bridge prompt remains visible;
- if the browser cannot confirm the submitted user message in its bounded observation window, status is `delivery_unconfirmed` and any exact retained Bridge prompt remains visible instead of being erased.

A later run may reuse a non-empty composer only when the previous Bridge state is recoverable and the composer text is byte-for-byte identical to the current Bridge prompt. Any operator edit, extra whitespace or unrelated draft blocks automatic reuse.

`delivery_unconfirmed` is diagnostic only. It does not disable the conversation, create `pendingDelivery`, clear the schedule, block controls, require a manual resolution decision or prevent removal.

For event wake, the exact `pendingWake` is separate from ambiguous-delivery state and remains durable until a delivery response is successful. This prevents a transient content/browser problem from losing the result-ready continuation signal.

## Active Local Agent task cancellation

The executor already supports repository-scoped `cancel_task` for an exact task id. The ChatGPT planner should use it when current run/status evidence already proves that a long-running task cannot achieve the intended outcome, rather than waiting for the task timeout. See `docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/EMERGENCY_CONTROLS.md`.

This is deliberately not a direct Bridge command. The Native Messaging host is notification-only and has no repository-write/executor command path.

## Popup

The popup exposes per chat:

- enable/pause switch;
- wake interval override;
- `Run now`;
- `Remove`.

Binding can be selected when adding the current chat. The same operator actions are also available from user-authored `LAB:OP:*` commands. To choose another repository for an existing chat, remove it and add it again; no implicit assistant rebind exists.

The global Master switch suspends scheduled alarms and Native Messaging watches without deleting per-conversation task-watch state or changing bindings.

## Worker module boundaries

`service_worker.js` is composition only:

- `worker_base.js` — shared protocol constants and small process-local registries;
- `worker_state.js` — serialized Chrome storage reads/writes;
- `worker_runtime.js` — runtime fetch/cache/validation;
- `worker_binding.js` — catalog binding lookup and prompt policy;
- `worker_schedule.js` — Chrome alarms and schedule reconciliation;
- `worker_transport.js` — tab discovery, content preflight and delivery authorization;
- `worker_event_wake.js` — durable task watches, recent events, pending event wakes and exact event routing;
- `native_events.js` — on-demand Native Messaging lifecycle, handshake/reconnect and ACK transport;
- `worker_event_diagnostics.js` — bounded read-only event-wake inspection data;
- `worker_controls.js` — assistant scheduling/maintenance control validation;
- `worker_delivery.js` — one normal/event feedback delivery lifecycle;
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
4. Copy the 32-character extension id shown by Chrome.
5. Register the Native Messaging host for exactly that id:

```bash
python scripts/chat_bridge_native_host.py install --extension-id <extension-id>
python scripts/chat_bridge_native_host.py status --extension-id <extension-id>
```

`status` must report `"healthy": true` with an empty `problems` array. It validates the manifest path/origin, wrapper registration, executable bit and expected restrictive file modes.

6. Open a concrete ChatGPT conversation.
7. Open the extension, select the exact repository binding and click **Add current chat**, or type an explicit user operator command such as `[LAB:OP:ADD=local-agent]`.
8. Use `LAB:CAPABILITIES`/`LAB:DEBUG` or `Run now` for an end-to-end Bridge check. After queueing a disposable Local Agent task, use `WAIT_TASK=<id>` to verify event wake.

To remove the host registration:

```bash
python scripts/chat_bridge_native_host.py uninstall
```

After pulling an extension update, click **Reload** on the extension card. Do not normally reload every open ChatGPT tab: worker-owned content refresh is expected to replace a reachable older protocol automatically. Reload the page only when Chrome has discarded/broken the tab or explicit diagnostics show content cannot be activated.

## Development validation

```bash
python scripts/verify.py --only bridge
python -m unittest tests.test_result_events tests.test_chrome_native_host tests.test_chat_bridge_native_host_installer
npm install --no-save --package-lock=false playwright@1.57.0
npx playwright install chromium
python scripts/verify.py --profile bridge-browser
```

Bridge validation includes protocol parsing, exact event routing, fast-task race recovery, duplicate/conflict handling, pending-event retry retention, pause/Master/operator lifecycle, MV3 restart persistence, Native Messaging framing/live post-handshake delivery, durable outbox integrity and installer diagnostics.

Browser smoke uses a disposable offline Chromium profile and the actual unpacked extension. It covers confirmed submission, composer replacement, draft preservation, SPA navigation, overlapping sends, retained/non-blocking recovery, popup behavior, service-worker restart, operator-control replay baselining and protocol-refresh regressions without contacting the operator's real ChatGPT session.

A green fixture/CI run does not prove the operator's currently loaded extension id/native-host registration. Before release, verify the exact candidate SHA and exact installed extension id on the real Mac.
