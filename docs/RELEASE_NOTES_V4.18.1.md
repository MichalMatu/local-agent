# Local Agent 4.18.1 / Chat Bridge 0.5.0

This patch keeps the released Python execution architecture and hardens browser wake delivery. It also makes direct GitHub editing an explicit planner path, completes Tracker onboarding and retires standalone C6 execution according to that repository's archival instructions.

## Bridge audit and corrections

- Journal each delivery before dispatch and authorize the exact token, tab, conversation, binding revision and generation immediately before clicking Send.
- Reject overlapping alarm/manual sends. Recheck SPA navigation and the unchanged composer, and preserve operator drafts.
- Confirm a new matching user message in the DOM. An unconfirmed click, missing protocol reply or worker interruption pauses with `delivery_uncertain`; restart never replays the journal. The operator resolves the observed outcome and resumes explicitly.
- Block Rebind/removal while a delivery is unresolved. Generation checks prevent late sends and controls from overwriting newer pause/schedule decisions.
- Accept privileged settings, Rebind and delivery-resolution operations only from the extension popup. Content controls require the exact top-frame conversation and current binding revision; pre-bootstrap assistant messages cannot control a new binding.
- A failed control acknowledgement can retry within a bounded attempt count. Stable message ids avoid duplicate controls when message lists change.
- Require remote runtime schema 3, unique identities and boolean execution flags. Remove schema 1/2 runtime parsing and the duplicate built-in identity catalog. Invalid/unavailable runtime fails closed; concurrent fetches share one bounded request.
- Serialize state/alarm changes and check generations before scheduling. Turning off the master switch clears all conversation alarms.

The durable journal follows Chrome's documented service-worker lifecycle: in-memory state can disappear when the worker stops. Content-script messages cross a separate authority boundary. References: [worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle), [extension messaging](https://developer.chrome.com/docs/extensions/develop/concepts/messaging).

## Planner and repository contract

Direct GitHub edits are valid when exact diff and relevant CI evidence verify the outcome. Local Agent is used for Mac command execution, local tools and devices. A hybrid verification task must explicitly check the committed SHA. Both paths obey the same conversation binding and repository branch policy; direct writes must not race an active local task on the same branch.

Tracker uses `be481b25-9d97-4205-b93f-95f5c5827441` and `~/agent-workspace/repos/tracker/{control,work,checkpoints}`. Its real onboarding probe completed on Local Agent 4.18.0 as `v4180-e2e-20260905T154547Z-onboarding-tracker`, digest `c6cf24718bcfee02d0f7f8317b365e13d657290b529ed927aa9f0ec6a7963073`. This proves execution/result publication, not an Android build or device test.

Standalone `esp32-c6-zigbee` retains its historical binding and workspaces but is disabled for execution. Its current `AGENTS.md` identifies `esp32s3_LiteGraph/firmware/extensions/zigbee-c6/` as the active source. No automatic conversation Rebind or workspace deletion is performed.

Downstream synchronization covers LiteGraph `AGENTS.md`, `LOCAL_AGENT_FLOW.md`, `LOCAL_AGENT_AUTOPILOT.md`; Growbox `AGENTS.md` on `main` and `mvp/environment-controller` plus that branch's `docs/STAGE27_NATIVE_IDF_HANDOFF.md`; MatrixHub `AGENTS.md` on `main` and `develop`; C6 archival `AGENTS.md`; and Tracker `AGENTS.md` on `main`. Release evidence records exact publication commits.

## Verification and deployment

Run `python scripts/verify.py`, `--profile macos-smoke` and `--profile bridge-browser` on the exact candidate. CI includes branch-aware coverage, Python 3.14 and isolated Chromium extension tests. Browser tooling is development-only and pinned to Playwright 1.57.0.

The browser fixture uses the actual extension in a disposable Chromium profile and verifies confirmed delivery, concurrent draft preservation, SPA navigation, overlapping sends, uncertain delivery and persistent recovery after browser/worker restart. It never sends a live ChatGPT message. Current live ChatGPT DOM compatibility and the operator's loaded extension version require separate verification.

After updating the unpacked extension source, reload its card in `chrome://extensions` and reload open ChatGPT tabs to install the matching content protocol. Existing schema-v3 bindings remain intact. Uncertain deliveries remain paused until explicitly resolved; do not clear stored state to bypass recovery.
