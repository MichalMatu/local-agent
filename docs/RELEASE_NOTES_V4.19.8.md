# Local Agent 4.19.8

## Summary

Fix Chat Bridge assistant controls for the live ChatGPT renderer variant where a logical `data-turn-key` can contain an assistant response without either `[data-user-message-bubble]` or an explicit assistant-role attribute.

## Root cause

The grouped-turn fallback admitted only turns that contained a recognized user bubble. Live inspection on the canonical diagnostic conversation showed one assistant-only turn with no user bubble, no `[data-conversation-role="assistant"]`, nineteen paragraph nodes and action buttons. The control scanner therefore never considered that newest assistant response even though binding, Run once, popup state and content-script readiness were healthy.

## Fix

- Admit grouped turns when residual text remains after bounded sanitization instead of requiring a user bubble.
- Remove recognized user bubbles and `button`/`[role="button"]` action controls from the cloned grouped turn before LAB parsing.
- Preserve fail-closed user-only behavior: once its user bubble is removed, a user-only turn has no residual assistant text and is rejected.
- Advance Chat Bridge to `0.5.17` and content protocol to `v13` so already-open v12 content contexts are detectably stale.
- Keep assistant guard protocol at `v7`; timeout/exhaustion guard behavior is unchanged.

## Evidence

- Live bounded CfT inspection reproduced the assistant-only grouped renderer on the canonical conversation.
- Focused `python3 scripts/verify.py --only bridge` passed.
- GitHub Actions real-extension `bridge-browser` passed the new assistant-only grouped-turn LAB regression together with test, coverage, Python 3.14 and macOS smoke gates.
