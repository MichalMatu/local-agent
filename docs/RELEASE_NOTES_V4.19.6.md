# Local Agent 4.19.6

## Summary

Fix Chat Bridge assistant-control discovery during mixed ChatGPT DOM rollouts where older turns retain explicit assistant-role nodes while newer turns expose only `data-turn-key` plus a recognized user bubble.

## Root cause

The 4.19.5 grouped-turn fallback was global: if any explicit assistant-role node existed anywhere in the mounted transcript, grouped assistant turns were ignored. ChatGPT can keep older explicit-role turns mounted while rendering a newer exchange only as a grouped turn, causing a new assistant `[LAB:*]` control to be invisible.

## Fix

- Merge explicit assistant nodes and grouped-turn fallbacks by logical turn and document order.
- Retain the explicit assistant node when both forms map to the same turn.
- Allow a newer grouped-only turn to supersede older explicit turns.
- Continue stripping user bubbles from a cloned grouped turn before assistant LAB parsing.
- Apply the same mixed-turn ordering contract to structured timeout/exhaustion discovery.
- Advance Chat Bridge to `0.5.15`, content protocol to `v11`, and assistant guard protocol to `v7` so already-open tabs replace the captured contracts after deployment.

## Regression

The real-extension browser suite keeps an older explicit assistant turn in the DOM, appends a newer grouped turn containing an assistant `[LAB:PAUSE]` plus an ordinary user bubble, and requires the newer assistant control to reach the worker.

## Rollback

`v4.19.5` remains the immediate production rollback point until this candidate is explicitly released.
