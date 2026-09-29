# Local Agent 4.19.7

## Summary

Fix Chat Bridge assistant controls that can be missed when the operator sends a newer user message before the bounded content-script scanner observes the immediately preceding assistant response.

## Root cause

The 4.19.6 grouped-turn discovery treated every `data-turn-key` containing a recognized user bubble as an assistant candidate. A newly appended user-only turn could therefore become the document-latest "assistant" candidate. After its user bubble was removed the residual assistant text was empty, the parser correctly found no control, and the scanner marked that empty candidate as scanned instead of returning to the preceding assistant `[LAB:*]` response.

This explains the live regression where popup binding and `Run now` worked while assistant `RESUME`, `STATUS`, `NEXT` and `PAUSE` controls remained silent.

## Fix

- Derive grouped assistant text by cloning the logical turn and removing recognized user bubbles.
- Admit a grouped turn to assistant ordering only when that residual assistant text is non-empty.
- Reuse the same extraction for assistant LAB parsing so selection and parsing cannot disagree.
- Advance Chat Bridge to `0.5.16` and content protocol to `v12` so already-open tabs replace `content.js` after deployment.
- Keep assistant guard protocol at `v7`; structured timeout/exhaustion discovery is unchanged in this release.

## Regression

The real-extension browser suite now appends a grouped assistant `[LAB:PAUSE]` response and, in the same page turn before the 600 ms scanner fires, appends a newer grouped turn containing only a user bubble. The test requires the preceding assistant control to update Bridge state exactly once.

## Rollback

`v4.19.6` remains the immediate production rollback point until this candidate is explicitly released.
