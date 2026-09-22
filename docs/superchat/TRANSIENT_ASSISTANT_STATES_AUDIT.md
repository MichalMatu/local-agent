# Transient assistant-state audit

Status: candidate-only analysis on `work/chat-bridge-live-chat-states`. Production `main` remains unchanged.

## Captured states

Three saved ChatGPT pages/screenshots from 2026-09-22 were reviewed.

Two captures represent the same transient transport state at different points in generation:

```text
Connection interrupted. Waiting for the complete answer
```

The complete saved DOM places that status inside the latest assistant turn, under a `.mask-shimmer-muted` status container, while ChatGPT still exposes its visible Stop control. One earlier capture contains only the screenshot because its saved HTML file is empty.

The third capture is a distinct long-thinking state:

```text
Our systems are thinking a bit more about this request before responding.
```

Its saved DOM uses the modern outer assistant-turn shape (`data-turn="assistant"`) and a `[data-streaming-response-status]` container. The UI also offers an optional action to retry with a faster model. That action is not the native assistant-delivery-timeout Retry control and must never be clicked automatically by Chat Bridge.

The long-thinking capture also demonstrates that a streaming assistant turn can exist without the legacy `[data-message-author-role="assistant"]` marker. The transient-state detector therefore prefers the modern `data-turn` shape and falls back to the legacy role marker.

## Candidate behavior

The candidate recognizes three transient/recovery states:

- `connection_interrupted` from the captured interruption status;
- `extended_thinking` from the captured long-thinking status;
- `stalled` only after ChatGPT continues to advertise active generation while the latest assistant-turn progress fingerprint remains unchanged for three minutes.

`extended_thinking` is wait-only. It blocks a fresh Bridge wake, uses the normal busy-retry cadence and never clicks the optional faster-model action.

`connection_interrupted` uses bounded escalation. The first observation only waits. After 45 seconds, if the same Bridge-owned episode is still present and ChatGPT is no longer generating, Chat Bridge submits one `Continue.` through the normal authorized composer delivery path. If the page remains interrupted for another minute after the continuation, or if it never becomes sendable and remains interrupted for two minutes, the worker may reload the preferred ChatGPT tab exactly once.

These recovery thresholds are independent of the normal conversation wake interval. The content guard scans the live conversation and proactively reports a current transient state to the service worker at most once every five seconds per signature. The service worker remains the authority for ownership, durable recovery budget and side effects. A ten-minute normal wake cadence therefore cannot turn a 45-second recovery threshold into a ten-minute delay.

`stalled` is a separate whole-tab recovery path. Once the generic no-progress detector has accumulated three minutes of unchanged assistant progress, a Bridge-owned stalled turn may trigger one whole-tab reload. Known transient states and the existing assistant-delivery-timeout card suppress the generic stall timer, so `extended_thinking`, `connection_interrupted` and native Retry recovery keep their dedicated policies.

The existing `message_delivery_timeout` contract remains separate. Only that exact error shape, with the proven native Retry control, can enter automatic assistant Retry recovery.

## Atomic reload contract

Whole-tab reload is deliberately atomic and bounded:

1. the worker verifies that the latest triggering user turn is Bridge-owned;
2. a non-empty composer blocks automatic recovery so an operator draft is never discarded;
3. the recovery episode is keyed by conversation URL, binding revision, generation and recovery kind;
4. the worker persists `reloadReservedAt` before calling `chrome.tabs.reload()`;
5. a repeated wake, proactive report or MV3 service-worker restart cannot reserve a second reload for the same episode;
6. a clean preflight retires the recovery episode, while add/rebind/delete and relevant conversation-setting changes clear stale recovery storage.

Automatic `Continue.` and reload are action-gated by ownership. A manually authored user turn can still be diagnosed as interrupted or stalled, but Chat Bridge does not continue or reload that turn automatically.

## Fail-closed rules

Classification of the captured states requires both the captured text and its captured structural container. Merely quoting either status text in a normal assistant answer must not classify the conversation.

Generic `stalled` requires all of the following at the same time: a visible active-generation Stop control, a stable latest assistant progress fingerprint for the full stall window, no recognized captured transient status and no recoverable native delivery-timeout card. Any assistant progress, generation end or recognized transient state resets the generic stall timer.

The optional faster-model action is explicitly outside the recovery contract because it changes model/capability rather than retrying the same transport operation.

If ChatGPT changes these structures, the detector should fail closed to the existing generic busy behavior rather than infer an unproven recovery action.

## Verification target

The candidate must prove:

1. both captured transient states are recognized;
2. neither captured state is treated as `message_delivery_timeout`;
3. `extended_thinking` remains wait-only and never clicks the faster-model action;
4. `connection_interrupted` performs bounded `wait -> Continue. -> single reload` recovery only for Bridge-owned turns;
5. a connection interruption that never becomes sendable may perform one atomic reload after the hard bound;
6. a proven generic no-progress stall may perform one atomic reload only for a Bridge-owned turn;
7. any assistant progress resets the generic stall timer;
8. a non-empty composer prevents automatic reload;
9. manual/unowned turns remain diagnostic-only;
10. reload reservation survives repeated wakes, proactive reports and service-worker restarts and prevents refresh loops;
11. recovery thresholds are driven by live proactive reports rather than the normal wake cadence;
12. normal wake delivery resumes and stale recovery state is retired after the transient state disappears;
13. existing timeout recovery and browser smoke remain green.
