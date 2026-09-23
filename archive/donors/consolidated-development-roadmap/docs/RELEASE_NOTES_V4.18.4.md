# Local Agent 4.18.4 / Chat Bridge 0.5.3

An assistant answer ending with `Acknowledged. [LAB:PAUSE]` previously failed to pause because the parser required the marker to occupy an entire line. The parser now accepts a whitespace-separated marker at the end of the final non-empty line. A separate marker line remains the recommended format. Quoted markers and markers followed by text remain invalid.

Generation detection now checks Stop-button visibility. A hidden retained button no longer blocks wake delivery or assistant control scanning. Visibility attribute changes trigger a control scan; a visible Stop button still blocks submission and defers controls until generation ends. The popup's `assistant_busy` label continues to represent the last delivery attempt, rather than a live generation indicator.

## Downstream documentation audit

Read the current GitHub versions of these registered documents before release:

- `MichalMatu/esp32s3_LiteGraph`, `main`: `AGENTS.md`, `LOCAL_AGENT_FLOW.md`, `LOCAL_AGENT_AUTOPILOT.md`.
- `MichalMatu/growbox-ml-controller`, `main` and `mvp/environment-controller`: `AGENTS.md`.
- `MichalMatu/MatrixHub`, `main` and `develop`: `AGENTS.md`.
- `MichalMatu/tracker`, `main`: `AGENTS.md`.

No downstream edit is required: none of these documents requires rejection of inline trailing controls or prescribes hidden-button generation detection. Their existing marker examples, conversation-scoped control semantics and canonical Local Agent links remain valid. The canonical control syntax is updated in `chat_bridge/README.md` and `docs/AUTONOMOUS_CHAT_LOOP.md`.

## Verification and operator test

Release gates are `python scripts/verify.py`, `python scripts/verify.py --profile macos-smoke` and the isolated Chromium fixture through `python scripts/verify.py --profile bridge-browser`. The fixture checks inline pause after generation, cleared scheduling, preserved interval and Master state, live popup updates, hidden-button delivery and visible-button blocking.

After updating the installed checkout, reload Local Agent Chat Bridge in `chrome://extensions`, then reload the open ChatGPT tabs to load the new content script. The extension version is `0.5.3`. Validation against the operator's live ChatGPT DOM remains a manual check; the reported hidden-button scenario was reproduced in an isolated browser fixture.
