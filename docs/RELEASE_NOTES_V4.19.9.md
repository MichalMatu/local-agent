# Local Agent 4.19.9

Fix a Chat Bridge 4.19.8 regression where a newer user-only grouped ChatGPT turn could shadow the preceding assistant LAB control when screen-reader-only UI chrome remained outside the recognized user bubble.

## Changes

- Ignore `.sr-only` accessibility chrome when deriving fallback assistant text from grouped `data-turn-key` turns.
- Preserve the 4.19.8 assistant-only grouped-turn fallback while restoring the 4.19.7 fail-closed user-only ordering guarantee.
- Add a real Chromium extension regression for `assistant control -> newer user-only turn with sr-only label`, requiring the preceding control to reach the worker.
- Advance Chat Bridge from 0.5.18 to 0.5.19 and content protocol from v13 to v14 so already-open reachable tabs replace the stale v13 content scanner.
- Keep assistant guard protocol at v8 because the repaired boundary is content control discovery; timeout/exhaustion DOM recovery behavior is unchanged.

## Verification

The focused candidate passed the complete GitHub CI matrix before the release-version bump, including 498 Python tests, Bridge protocol/unit validation, Python 3.14, coverage, macOS smoke, and the real Chromium extension browser suite. The browser suite explicitly reported `PASS: sr-only user chrome cannot shadow the preceding assistant control`.

The final 4.19.9 candidate must pass the same full matrix again on the exact versioned candidate SHA before any decision to advance `main`.
