# Changelog

This changelog records operationally relevant Local Agent releases. The release tag and `local_agent.version.RELEASE_VERSION` are the version source of truth. Historical per-release notes remain available under `docs/`.

## v4.18.18

- Fixed the live Chat Bridge 0.5.6 diagnostic-feedback submit regression where `[LAB:HELP]` was detected and `[LA_BRIDGE_FEEDBACK]` was inserted into the composer but the operator still had to press Send manually.
- Advanced Chat Bridge to 0.5.7 / content protocol v6 and made service-worker activation probe configured open ChatGPT tabs, re-injecting only unavailable/protocol-mismatched content so an unpacked-extension Reload can upgrade an already-open v5 tab without reloading ChatGPT or sending a wake.
- Changed the browser submit path to re-resolve the current enabled ChatGPT Send button immediately before submission and use its DOM `click()` path first; `form.requestSubmit()` remains last-resort fallback only.
- Protect the actual post-insertion contenteditable text snapshot so editor whitespace canonicalization does not masquerade as an operator edit; any later composer change still fails closed before submission.
- Preserved exact-conversation/operator-edit/wrong-conversation/authorization guards and non-blocking `delivery_unconfirmed` behavior; no blind Enter simulation or unbounded resubmission was added.
- Added submit-path, startup stale-content refresh and deterministic isolated Chromium `[LAB:HELP]` auto-submit regressions. See `RELEASE_NOTES_V4.18.18.md`.

## v4.18.17

- Fixed the live Chat Bridge 0.5.5 popup regression where `Add current chat` still hard-coded content protocol v3 and rejected an already-open reachable protocol-v4/v3-mismatched tab with a manual-reload error.
- Centralized `CONTENT_PROTOCOL_VERSION` in `control_protocol.js`, advanced Chat Bridge 0.5.6 content protocol from v4 to v5 so already-open 0.5.5 tabs are detectably stale, and routed popup tab activation through the worker's dispose/inject/re-probe path; popup no longer owns a second protocol version or reinjection implementation.
- Added Chat Bridge 0.5.6 LAB discovery/diagnostic controls (`HELP`, `CAPABILITIES`, `STATUS`, `DEBUG`, `SETTINGS`, `CHATS`, `CHAT=<id>`) with read-only same-chat feedback and infrastructure-only global chat listing.
- Added explicit user-authored `LAB:OP:*` chat management for ADD/REMOVE/ENABLE/DISABLE/INTERVAL/Bridge reload, with persistent bounded dedupe, historical-user-message baselining across reinjection/navigation, and assistant/operator privilege separation so assistant content cannot mutate repository binding.
- Added direct regression coverage for reachable 0.5.5/protocol-v4 content -> 0.5.6 worker refresh -> protocol-v5 readiness without a ChatGPT page reload, plus command-catalog/operator-control, exhaustion-guard cleanup, and operator-replay tests. See `RELEASE_NOTES_V4.18.17.md`.

## v4.18.16

- Hardened Chat Bridge delivery with content protocol v4 / extension 0.5.5: stale reachable content scripts are reinjected automatically, unconfirmed Bridge-owned prompts remain visible, and exact retained prompts can be reused only when untouched by the operator.
- Replaced the assistant-control scanner's fixed three-failure give-up with a pure bounded 5-30 second retry policy that never terminally exhausts for unchanged assistant content.
- Preserved explicit `NEXT=30s` protocol compatibility while changing autonomous healthy-task pacing to no sooner than about two minutes for early liveness checks and normally 5-10 minutes for multi-minute builds/tests.
- Directed the planner to use existing repository-scoped `cancel_task` when exact run/status evidence already proves an active task cannot succeed; executor ownership and Browser Bridge authority remain unchanged.
- Added protocol/injection, retry, pacing and isolated Chromium regressions, including direct proof that an unconfirmed Bridge prompt stays visible and operator edits block automatic reuse. See `RELEASE_NOTES_V4.18.16.md`.

## v4.18.15

- Fixed parallel self-update starvation when `.agent/daemon/control.json` retains a repository-owned `cancel_task` after that request has already been acknowledged or otherwise completed.
- Preserved repository-worker ownership of `cancel_task`; the supervisor still does not route it through global control handling or use it to drain unrelated workers.
- Decoupled `maybe_self_update()` from the cancel dispatch guard so a stale cancel control slot cannot pin an otherwise clean installed `main` checkout to an older release.
- Added focused regression coverage and explicit macOS smoke coverage; retained the 4.18.14 BUG-002 admission semantics unchanged. See `RELEASE_NOTES_V4.18.15.md`.

## v4.18.14

- Fixed BUG-002 so repeated control-probe lease contention caused by the supervisor's own active control-repository worker no longer collapses unrelated cross-repository admission.
- Track true consecutive `LEASE_BUSY` outcomes separately from degraded `DEFERRED` probes; degraded probes reset the lease-busy streak while preserving bounded control retry/backoff.
- After six consecutive known-worker `LEASE_BUSY` outcomes, pause only new control-repository admission so the supervisor can regain the control lease before starting another control task; unrelated repositories remain admissible when capacity exists.
- Preserve the six-consecutive-busy defensive global drain for unexplained control-repository lease holders and the immediate drain for confirmed `PENDING` global control.
- Move control-probe retry/admission state and pure `RETRY` / `PAUSE_CONTROL_REPOSITORY` / `DRAIN_ALL` policy into `local_agent.supervisor.scheduling`, leaving `orchestrator.py` responsible for side effects and worker coordination.
- Add pure policy regression tests, real temporary-Git late-admission overlap coverage, macOS smoke coverage, current-documentation drift checks and release metadata checks. See `RELEASE_NOTES_V4.18.14.md`.

## v4.18.13

- Increased the generated macOS LaunchAgent `ExitTimeOut` to 15 seconds and the restart helper bootout wait budget to 20 seconds so launchd does not SIGKILL the guarded entrypoint before bounded supervisor cleanup can finish.
- Retained four-worker launchd rendering and the scheduler hard cap of four.
- Preserved task schema, resource classification, binding, watchdog, result and downstream planner contracts.
- Frozen known-working release commit: `a32e54858c3bcb9687334b3232b71ae6ff130208`. See `RELEASE_NOTES_V4.18.13.md` and `PRODUCTION_BASELINE_V4.18.13.md` on the control-probe fix candidate branch.

## v4.18.12

- Removed the duplicated historical macOS `1..3` worker limit from LaunchAgent generation.
- Reused `local_agent.supervisor.scheduling.MAX_MAX_WORKERS` so runtime admission and macOS deployment validation share the same hard cap of four.
- Added direct builder and CLI render regression coverage for `--max-workers 4`. See `RELEASE_NOTES_V4.18.12.md`.

## v4.18.11

- Raised bounded parallel repository concurrency from three to four workers while keeping the default at one.
- Preserved repository leases, named/machine resource exclusion, worker ordering, watchdogs, control synchronization, task contracts and result schemas.
- Added direct coverage for accepting four workers and rejecting five. See `RELEASE_NOTES_V4.18.11.md`.

## v4.18.10

- Announce worker admission before acquiring leases, and publish the registered worker set before returning from dispatch.
- Accept watchdog lease observations only when the same idle status snapshot remains current before and after the probe.
- Cover real worker dispatch and task completion, failed admission, and status changes during probing. See `RELEASE_NOTES_V4.18.10.md`.

## v4.18.9