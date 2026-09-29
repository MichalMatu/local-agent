# Local Agent Chat Bridge

Chrome Manifest V3 extension for binding one ChatGPT conversation to Local Agent, scheduling bounded wake-ups, exposing explicit conversation controls, and recovering a small set of typed assistant-side failures.

The current production baseline is:

```text
Local Agent:     v4.19.8
Chat Bridge:     0.5.18
content protocol: v13
assistant guard:  v8
```

Canonical behavior is defined by the current source plus:

- `docs/GOLDEN_STANDARD.md`
- `docs/AUTONOMOUS_CHAT_LOOP.md`
- `docs/HOST_OPS_MULTIREPO.md`
- `docs/CHATGPT_DOM_CONTRACT.md`
- `docs/CHAT_BRIDGE_HANDOFF_2026-09-29.md` for the field-test handoff that produced v4.19.8

Historical release notes document old behavior at the time of each release. They are not the current Bridge contract.

## Binding model

Every configured conversation stores one current Bridge binding: repository id, repository name, canonical `agent_binding`, binding revision, pacing state and alarm state.

The binding is immutable **within one binding revision and wake envelope**, not immutable forever. It changes only through an explicit binding mutation:

```text
assistant: [LAB:ADD=<repository-id>]
assistant: [LAB:REBIND=<repository-id>]
assistant: [LAB:REMOVE]
operator:  [LAB:OP:ADD=<repository-id>]
operator:  [LAB:OP:REMOVE]
popup:     Add current chat / Remove
```

`ADD` accepts only an exact repository id from the validated runtime catalog. Assistant `ADD` creates the conversation enabled; popup and `OP:ADD` use conservative disabled onboarding. `REBIND` explicitly changes an already-configured conversation and creates a fresh binding/bootstrap boundary. `REMOVE` deletes that conversation's Bridge configuration.

Normal pacing, inspection and maintenance controls do not change repository identity. The global **Master** switch is never changed by assistant controls.

### Planner scope

```text
planner_scope=repository -> planner may target only the bound repository
planner_scope=multirepo  -> planner may target repositories in the current validated runtime catalog
```

The canonical `host-ops` binding is the multirepo operator workspace. A `host-ops` conversation stays bound to `host-ops` while normal work may target another catalog repository. Every Local Agent task still carries the exact canonical binding of its **target** repository.

The `local-agent` catalog entry is intentionally `execution_enabled: false`: it may be inspected or edited through direct GitHub operations, but project tasks must not be queued against that binding.

## Wake envelope

Every bootstrap/compact wake contains the stored conversation identity:

```text
[LA_AGENT=<conversation binding UUID>]
[LA_REPO=<conversation repository id>]
[LA_REPOSITORY=<owner/name>]
[LA_CHAT=<conversation id>]
```

The first wake after add/rebind establishes the bootstrap boundary. Later wakes use the compact wake prompt. A configured ChatGPT conversation must remain open in Chrome; it does not need to be foregrounded.

## LAB command surface

`control_protocol.js` is the single command catalog and owns `CONTENT_PROTOCOL_VERSION`.

### Assistant inspection

```text
[LAB:HELP]
[LAB:CAPABILITIES]
[LAB:STATUS]
[LAB:DEBUG]
[LAB:SETTINGS]
[LAB:CHATS]
[LAB:CHAT=<chat-id>]
```

Successful inspections return a Bridge-generated user message beginning with `[LA_BRIDGE_FEEDBACK]`.

### Assistant binding mutations

```text
[LAB:ADD=<repository-id>]
[LAB:REBIND=<repository-id>]
[LAB:REMOVE]
```

These are explicit state-changing controls, not read-only diagnostics. Exact sender URL, top-frame origin, catalog identity and persistent dedupe are revalidated in the worker.

### Assistant pacing

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:NEXT=2m]
[LAB:NEXT=10m]
[LAB:INTERVAL=30m]
[LAB:INTERVAL=AUTO]
```

`NEXT` arms/re-arms only this conversation and changes its next wake. The wire protocol accepts 30 seconds through 24 hours, but autonomous healthy-task polling should normally use at least about two minutes, and 5-10 minutes for multi-minute builds/tests unless exact evidence justifies a nearer check.

### Bridge-local maintenance

```text
[LAB:RELOAD=CONTENT]
[LAB:RELOAD=BRIDGE]
[LAB:RESTART=WORKER]
```

`RESTART=WORKER` aliases Bridge runtime reload because Chrome does not expose a public API to restart only one MV3 service worker.

### User-authored operator namespace

Processed only from a user-authored message in the exact top-frame conversation:

```text
[LAB:OP:ADD=<repository-id>]
[LAB:OP:REMOVE]
[LAB:OP:ENABLE]
[LAB:OP:DISABLE]
[LAB:OP:INTERVAL=<minutes|AUTO>]
[LAB:OP:RELOAD=CONTENT]
[LAB:OP:RELOAD=BRIDGE]
```

The assistant parser rejects `LAB:OP:*`, and the operator parser rejects assistant controls. Operator-command dedupe is durable and bounded.

## Assistant-control parsing

A control is parsed from the final supported marker in the latest assistant response. Text may precede the marker. After the marker only whitespace and a bounded set of punctuation/Markdown decorations are accepted; later letters, digits, emoji or unrelated text reject the candidate. A malformed final candidate does not fall back to an earlier marker.

Transient assistant-control delivery failures retry unchanged assistant content with bounded backoff instead of permanently exhausting after a small fixed attempt count.

## Current ChatGPT DOM contract

Bridge supports three observed assistant representations:

1. legacy `[data-message-author-role="assistant"]`;
2. current `[data-conversation-role="assistant"]`;
3. bounded grouped-turn fallback on `[data-turn-key]` when no explicit assistant node exists for that logical turn.

The grouped fallback does **not** require a user bubble. v4.19.8 live evidence showed assistant-only turns containing assistant paragraphs/action controls with neither a user bubble nor an explicit assistant-role marker. Bridge clones the turn, removes recognized user bubbles and action controls, and accepts the turn as assistant content only when residual assistant text or a recognized structured assistant error remains. User-only shells therefore remain fail-closed.

When explicit and grouped representations coexist, Bridge merges them by logical turn and document order; an explicit assistant node wins only inside the same logical turn. An older explicit node must not hide a newer grouped-only assistant turn.

See `docs/CHATGPT_DOM_CONTRACT.md` for the authoritative selectors and terminal-error rules.

## Delivery model

Bridge keeps no durable ambiguous-delivery journal for normal wake submission.

- confirmed submitted user DOM -> `sent`;
- no usable Send button in the bounded window -> `send_button_not_ready`;
- submission happened but the exact user message cannot be confirmed -> `delivery_unconfirmed`.

`delivery_unconfirmed` is diagnostic only. It does not disable the conversation or block controls.

A retained Bridge prompt may be reused only when the composer still matches it byte-for-byte. Any operator edit blocks automatic reuse.

## Recoverable assistant terminal errors

The assistant guard recognizes exactly these typed terminal errors:

```text
Message delivery timed out. Please try again.
Resume stream unavailable
```

Both require a structured assistant error card and ChatGPT's native Retry control. Unknown Retry-looking errors fail closed.

Automatic Retry is narrower than detection: the worker requires the exact preferred tab, exact conversation URL, current binding revision/generation, enabled Master/conversation state, and a triggering user message owned by Bridge. Manual user prompts may be diagnosed but are never automatically retried.

The durable retry budget is three authorized native Retry clicks:

```text
1: 1.5 s
2: 5 s
3: 15 s
```

After exhaustion the conversation is disabled as `assistant_retry_exhausted` and its alarm is cleared. While a recognized error is unresolved, `Run now` and scheduled wakes return `assistant_recovery_pending` instead of stacking another user message.

## MV3 update/reload rule

A ChatGPT page reload is **not** a substitute for reloading an unpacked MV3 extension runtime. During the 2026-09-29 field test, a stale service worker still reported an older protocol while freshly injected page scripts were newer, producing `content_script_protocol_mismatch`.

For source/protocol upgrades:

- normal worker-owned activation may replace reachable stale content/guard scripts;
- if the MV3 service worker itself is stale, reload the Bridge runtime (`RELOAD=BRIDGE`, extension reload, or restart the dedicated diagnostic CfT profile);
- verify worker/content/guard versions again before interpreting later failures.

External recovery and managed diagnostic-browser stop are fail-closed while ChatGPT exposes an active generation Stop control. Explicit `--force` is reserved for deliberate emergency interruption.

## Popup

The popup exposes:

- current-chat repository selection/add;
- per-chat enable/pause;
- wake interval override;
- `Run now`;
- `Remove`;
- global Master switch.

Popup add is conservative and initially disabled. This is independent from assistant `ADD`, which creates the exact binding enabled.

## Install / diagnostic profile

For normal manual installation:

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Load unpacked `chat_bridge/`.
4. Open one concrete `/c/<id>` ChatGPT conversation.
5. Bind it through popup, user-authored `LAB:OP:ADD`, or explicit assistant `LAB:ADD`.

For the maintained diagnostic environment, use the dedicated Chrome-for-Testing profile and the repository Host Ops helpers. Do not reuse or mutate the user's daily Chrome profile merely to recover Bridge diagnostics.

## Verification

Focused Bridge verification:

```bash
python scripts/verify.py --only bridge
```

Real-extension browser verification:

```bash
python scripts/verify.py --profile bridge-browser
```

A release that changes Bridge runtime behavior still requires the repository's full CI matrix and macOS smoke according to `AGENTS.md` and `docs/GOLDEN_STANDARD.md`.
