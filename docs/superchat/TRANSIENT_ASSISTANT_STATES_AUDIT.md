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

The candidate adds recognition-only transient-state classification:

- `connection_interrupted`
- `extended_thinking`

A recognized transient state blocks a fresh Bridge wake and uses the normal busy-retry scheduling cadence. It does not consume the assistant delivery-timeout Retry budget, does not submit a replacement user prompt, and does not click any page action.

The existing `message_delivery_timeout` contract remains separate. Only that exact error shape, with the proven native Retry control, can enter automatic assistant Retry recovery.

## Fail-closed rules

Classification requires both the captured text and its captured structural container. Merely quoting either status text in a normal assistant answer must not classify the conversation.

The optional faster-model action is explicitly outside the recovery contract because it changes model/capability rather than retrying the same transport operation.

If ChatGPT changes these structures, the detector should fail closed to the existing generic busy behavior rather than infer an unproven recovery action.

## Verification target

The candidate must prove:

1. both captured transient states are recognized;
2. neither state is treated as `message_delivery_timeout`;
3. no new Bridge wake is submitted while either state is present;
4. no assistant-recovery Retry kick is issued for either state;
5. normal wake delivery resumes after the transient state disappears;
6. existing timeout recovery and browser smoke remain green.
