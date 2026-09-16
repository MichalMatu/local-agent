# Local Agent bug backlog

This file tracks confirmed or strongly evidenced Local Agent defects that still need engineering or release work.

`CHANGELOG.md` records release-target/shipped changes. This backlog records **known problems, candidate state and closure evidence** until a defect is released and verified.

## Workflow

For every newly discovered bug, record:

- a stable bug id and priority;
- observed symptoms and reproduction evidence;
- user/operator impact;
- the most likely technical cause, clearly marked when not yet proven;
- the intended repair direction;
- regression tests required before closing the item.

When a bug is fixed:

1. keep the backlog entry, mark it `Fixed`, and add the fixing commit/release;
2. add the shipped behavior change to `CHANGELOG.md` / release notes as appropriate;
3. retain regression coverage so the same failure cannot silently return.

A green candidate branch is not yet `Fixed` when production `main` has not advanced. Use `Candidate validated` until merge/tag/live verification completes.

Priorities:

- **P0** — safety/data-integrity failure or uncontrolled execution risk;
- **P1** — blocks normal Local Agent operation or requires disruptive manual recovery;
- **P2** — degraded reliability/usability with a practical workaround;
- **P3** — minor defect or hardening opportunity.

---

## BUG-001 — orphan descendant can retain `machine` / resource flock after worker failure

**Status:** Open  
**Priority:** P1  
**First confirmed:** 2026-09-06  
**Area:** parallel supervisor, process lifecycle, resource admission, cancellation/recovery

### Symptom

A repository task running Playwright/Vite became stuck. The active task could no longer be cancelled reliably through the normal control path. After restarting/updating Local Agent, the next LiteGraph task remained indefinitely in:

```text
state = waiting_resource
blocked_resources = ["machine"]
```

Restarting the Local Agent service was insufficient. A full macOS reboot released the resource and the LiteGraph repository returned to `idle`.

### Evidence / current mechanism

Local Agent resource admission uses `fcntl.flock`, not a lock-file-existence check. Resource lease file descriptors are intentionally inherited by spawned descendants through `LOCAL_AGENT_RESOURCE_LEASE_FDS` / `pass_fds`.

This protects against unsafe overlap when a worker dies while its command tree is still alive. Existing crash-recovery tests intentionally verify that a lease remains held until an orphaned command exits.

The failure mode is therefore consistent with a worker or control path dying while a descendant such as Playwright, Vite, Node or Chromium survives and continues holding the inherited resource descriptor.

### Impact

- an otherwise healthy supervisor can report `waiting_resource` forever;
- unrelated work requiring `machine` is blocked;
- normal Local Agent restart/update may not recover the machine;
- the operator may be forced to find/kill orphan processes manually or reboot macOS;
- the state looks like resource contention even when the original task is no longer productively running.

### Safety constraint

**Do not recover by deleting `machine.lock` or resource lock files.**

The kernel-held `flock`, not the pathname, is the exclusion mechanism. Deleting/recreating the file while an old process still holds the original inode could allow unsafe concurrent execution.

### Planned repair

1. Persist enough active-attempt process ownership metadata to identify the Local Agent-owned process group (`pid`/`pgid`) and associated resource lease without relying only on in-memory worker state.
2. On explicit `cancel_task`, bounded supervisor shutdown/restart, and stale-attempt startup recovery, detect surviving descendants belonging to the exact Local Agent attempt.
3. Terminate only the owned process group: bounded `SIGTERM`, then `SIGKILL` if required. Never kill processes merely because their executable name is `node`, `vite`, `chromium`, `playwright`, etc.
4. Verify the owned process group is gone and the resource lease is actually acquirable before retrying pending work.
5. Improve diagnostics for `waiting_resource` so the operator can see the known holder/attempt PID or PGID when Local Agent can determine it.
6. Preserve the existing fail-closed rule: interrupted claimed work must not be silently replayed, and resource cleanup must never create overlapping execution.
7. Keep cancellation and recovery functional even when the original repository worker no longer responds to the control watcher.

### Required regression coverage

- worker dies while a descendant still holds `machine`; controlled recovery releases it without a macOS reboot;
- the same case for a named resource;
- explicit `cancel_task` kills the exact owned descendant process group and receives/publishes a terminal ACK;
- supervisor restart cleans a stale owned descendant without touching unrelated user processes;
- an unrelated process with similar executable names is never killed;
- no second task can acquire the resource until the old owned command group is confirmed dead;
- interrupted work remains terminal/fail-closed rather than being silently re-executed;
- macOS smoke covering a realistic Playwright/Vite/Chromium descendant tree;
- existing resource-wait and crash-recovery tests continue to pass or are deliberately updated to the new ownership/recovery contract.

### Temporary operator recovery

Until this is fixed:

1. disable Local Agent before disruptive recovery;
2. inspect the holder rather than deleting lock files;
3. kill only a positively identified orphan Local Agent process tree when practical;
4. if ownership cannot be established safely, a macOS reboot is an acceptable last-resort recovery;
5. confirm the resource is no longer held, then re-enable Local Agent and verify repository status returns to `idle` or expected work.

### Closure criteria

This item can be marked `Fixed` only when the exact failure can be reproduced in an automated/integration test and recovered without rebooting the Mac, while preserving resource exclusion and no-replay guarantees.

---

## BUG-002 — active control-repository lease contention drains unrelated parallel admission

**Status:** Candidate validated; pending v4.18.14 merge/tag/live verification  
**Priority:** P1  
**First confirmed:** 2026-09-08  
**Area:** parallel supervisor, global control probe, repository admission

### Symptom

A long task in the supervisor control repository runs with `resources: []`, while another repository has a valid pending task with `resources: []` and unused worker capacity. Under v4.18.13, the second repository may remain unstarted for minutes and then begin shortly after the control-repository task finishes.

This makes production appear as if another repository is "holding the whole agent" even though neither task requested `machine` or a conflicting named resource.

### Evidence / reproduction

The v4.18.13 supervisor probes the designated control repository periodically while workers are active. The probe tries to acquire that repository's execution lease. When the control repository itself has an active worker, that worker correctly owns the same lease, so the probe returns `LEASE_BUSY`.

After repeated lease-busy outcomes, v4.18.13 can enter global control pending/drain state. While that state is active and any worker is still running, the main loop continues before normal repository admission. Unrelated repository tasks are therefore not started until the active worker set becomes empty.

Production evidence confirmed the pattern with LiteGraph as the control repository and Growbox as the waiting repository. Both tasks used `resources: []`; worker capacity was available; the Growbox task started only after the long LiteGraph task ended.

The original short two-repository parallel barrier test did not expose the defect because it finished before the global-control probe/backoff path could accumulate enough lease contention.

### Impact

- cross-repository parallelism can collapse during sufficiently long control-repository tasks;
- pending tasks can wait well beyond the nominal repository poll interval despite free worker capacity;
- operators can misdiagnose the delay as RAM pressure, `machine` contention or a dead poll loop;
- production `max_workers=4` is not reliably usable for ordinary independent work on v4.18.13;
- development throughput is materially degraded.

### Non-cause: RAM admission

`memory_limit_mb` is not a scheduler-wide reservation. It is enforced inside an already-running task by process-group RSS sampling. The parallel supervisor does not sum task memory limits and does not block another repository because aggregate host RAM or requested per-task memory exceeds a scheduler threshold.

### v4.18.14 candidate repair

The v4.18.14 candidate implements the repair in the existing scheduling ownership boundary instead of adding another state machine to `orchestrator.py`:

1. `local_agent.supervisor.scheduling.ControlDeferralState` owns control retry/admission evidence.
2. Overall deferred-probe count drives bounded 2-15 second retry/backoff; a separate **consecutive `LEASE_BUSY`** streak drives lease-starvation protection.
3. A `DEFERRED` sync/network/ACK-read outcome breaks the lease-busy streak while retaining bounded retry behavior.
4. Fewer than six consecutive `LEASE_BUSY` outcomes retry without changing admission.
5. On the sixth consecutive `LEASE_BUSY`, a known active control-repository worker causes only **new control-repository admission** to pause. Existing workers continue and unrelated repositories remain admissible when capacity/resources permit it.
6. That pause gives the supervisor a control-probe opportunity after the active control worker releases its lease, preventing a continuous control-repository queue from starving global control.
7. Six consecutive `LEASE_BUSY` outcomes with no corresponding known active control worker retain the defensive global drain for unexplained/stale lease ownership.
8. A confirmed `PENDING` global control request still drains immediately.
9. A configured control-repository identity change clears stale retry/lease-busy/pause evidence and invalidates the previous control-poll clock.
10. `resources: ["machine"]` priority/drain semantics, named-resource locking, repository leases, claims/results, hard binding, emergency disable and self-update behavior are unchanged.

### Candidate regression coverage

Implemented on `fix/control-probe-parallel-admission`:

- pure policy coverage for five lease-busy retries and the sixth known-worker pause;
- pure policy coverage for the sixth unexplained lease-busy defensive global drain;
- mixed sequence coverage proving `5 × LEASE_BUSY -> DEFERRED -> LEASE_BUSY` leaves a lease-busy streak of one rather than seven;
- control-repository identity-change/reset coverage;
- real temporary-Git integration test that keeps the control task alive, crosses the six-consecutive-busy threshold, queues a second repository afterwards and requires that second task to start before the control task is released;
- explicit integration evidence that the known-worker path logs `pausing new control-repository admission` with `consecutive_lease_busy=6` and does not log the global-drain path;
- full existing parallel/resource/repository lease regression suite through normal CI;
- exact-candidate macOS smoke includes both the pure policy and real overlap regression modules;
- current-documentation and release-metadata drift checks are part of the suite.

### Temporary operator workaround

Until v4.18.14 is merged/tagged and production is verified live, v4.18.13 remains the running baseline. Avoid assuming `max_workers=4` guarantees admission while a long task is running in the designated control repository. No restart is required merely because a waiting task is delayed; allowing the control-repository task to finish normally releases the current condition.

For rollback, use release tag `v4.18.13` or branch `rollback/v4.18.13-known-working`, both pointing to commit `a32e54858c3bcb9687334b3232b71ae6ff130208`.

### Closure criteria

Mark this item `Fixed` only after all of the following are true:

1. the exact final v4.18.14 candidate passes focused control-admission tests, the complete CI matrix and macOS ARM64 smoke/recheck;
2. downstream documentation audit has no material contradiction;
3. the validated candidate is explicitly merged to `main` and tagged `v4.18.14`;
4. the live daemon reports the released version/revision;
5. live production evidence demonstrates independent repository admission while a sufficiently long control-repository task is active, or an equivalent exact released-code E2E is recorded.

---

## BUG-003 — historical conversation-limit message can disable an active Chat Bridge chat

**Status:** Candidate patch on `feature/chat-bridge-event-wake`; not yet released  
**Priority:** P1  
**First confirmed:** 2026-09-16  
**Area:** Chat Bridge, exhaustion detection, DOM contract

### Symptom

A configured Chat Bridge conversation can unexpectedly become `enabled=false`, with its alarm removed, even though the current conversation is still active and usable.

### Evidence / reproduction

The exhaustion detector introduced in commit `a3b78b35817a01b824f3d2ffb5012ad1a2d989ae` scanned assistant messages from newest to oldest until it found any historical error containing `You've reached the maximum length for this conversation` plus a `Start new chat` button. A stale historical error retained in the DOM could therefore be treated as current exhaustion.

`reportConversationExhausted()` then sets `enabled=false`, clears `nextRunAt`, increments generation and clears the conversation alarm. A later pacing command such as `INTERVAL` can overwrite `lastStatus` while preserving the disabled state, obscuring the original exhaustion status in diagnostics.

The operator observed exactly the resulting disabled/no-schedule state during the 2026-09-16 background-tab investigation. That live observation is consistent with this defect, although the original exhaustion transition itself was not captured in a historical state log.

### Candidate repair

On the working branch, exhaustion detection was narrowed so only the **latest assistant message** may qualify as current conversation exhaustion. Regression coverage now requires that an old exhaustion message followed by a newer normal assistant message returns no exhaustion.

Candidate extension version: `0.5.13`.  
Candidate code head after the focused patch/version bump: `4f2d7e76cc68f008034226ae4a89a519470ffbc6`.

### Required regression coverage

- latest assistant message is the exact exhaustion UI -> detected;
- older exhaustion message followed by a newer normal assistant message -> not detected;
- unrelated error plus `Start new chat` -> not detected;
- exhaustion text without the expected button -> not detected;
- live chat remains enabled/scheduled after reload with a stale historical limit message in DOM.

### Closure criteria

Mark `Fixed` only after the exact candidate passes CI, is explicitly released/merged, and live verification confirms a stale historical limit message cannot disable an otherwise active chat.

---

## BUG-004 — interval scheduler does not reliably wake an inactive ChatGPT tab

**Status:** Open; known issue intentionally deferred  
**Priority:** P1  
**First confirmed:** 2026-09-16  
**Area:** Chat Bridge, Chrome alarms, background-tab scheduling

### Symptom

A configured conversation with a short interval can fail to produce the expected scheduled wake while the operator is working on another browser tab. Returning to the ChatGPT tab may make the timing/UI appear to advance, but the expected autonomous interval wake was not observed while the tab remained inactive.

### Evidence / reproduction

The failure was reproduced with the conversation enabled and an interval override during a deliberate background-tab test. Chrome Memory Saver and Energy Saver were disabled and the ChatGPT site was allowed to stay active, so those user-facing optimization settings do not explain the observed failure.

Two control tests succeeded while the ChatGPT tab was inactive:

1. `Run now` delivered `[LA_WAKE]` to the inactive conversation.
2. An exact synthetic `task_result_ready` event for `e2e-bg-event-20260916-1910`, armed with `WAIT_TASK`, delivered `[LA_WAKE]` to the inactive conversation through the Native Messaging/event path.

Therefore background **message injection/delivery itself works**. The remaining defect is specifically in the ordinary interval/scheduler path or its transition into delivery, not in the general ability to send into an inactive ChatGPT tab.

### Impact

- normal periodic Chat Bridge tracking cannot currently be trusted when the operator works in another tab;
- event-driven exact task wakes still work in the tested background-tab case;
- `Run now` remains a manual workaround;
- diagnosing this as generic Chrome background-tab blocking would be misleading based on current evidence.

### Deferred repair direction

Do not fix during the current branch-freeze/cleanup pass. When resumed, compare the exact `Run now` path with the `chrome.alarms.onAlarm` path and instrument the handoff from alarm firing to delivery authorization. Add a browser regression where the configured ChatGPT tab is present but inactive for longer than the chosen interval.

### Required regression coverage

- inactive configured tab receives an ordinary interval wake without user focus change;
- active and inactive tab cases use the same hard-bound conversation identity;
- `Run now` and event-driven delivery remain unaffected;
- no permanent high-frequency polling is introduced as a workaround.

### Closure criteria

A real inactive-tab interval run must wake the chat autonomously at the expected bounded cadence, with diagnostic evidence showing the alarm-to-delivery path completed without requiring a focus change.

---

## BUG-005 — some Chat Bridge state/content transitions still require manual `Ctrl+R`

**Status:** Open; known issue intentionally deferred  
**Priority:** P2  
**First confirmed:** 2026-09-16  
**Area:** Chat Bridge, content-script lifecycle, page/runtime refresh

### Symptom

In some Bridge reload/recovery scenarios, the ChatGPT conversation does not immediately reflect the expected current Bridge/content-script state until the operator manually refreshes the page with `Ctrl+R`.

### Evidence / reproduction

Manual page refresh has been required during live recovery/testing to make the conversation use or expose the expected current state. The exact minimal trigger is not yet isolated well enough to attribute this to one code path, so this item is intentionally recorded without a speculative root cause.

The current event-driven branch already contains bounded cold-start reconciliation and content-script refresh logic, but the operator still identified manual `Ctrl+R` as a remaining practical issue after the event-wake work.

### Impact

- operator may need an unexpected manual page refresh after a Bridge/content transition;
- it weakens confidence in zero-touch recovery even when transport/runtime state itself is healthy;
- it can obscure whether a failure belongs to service-worker state, content-script freshness or page state.

### Deferred repair direction

Do not change behavior during the current cleanup pass. First produce a minimal deterministic reproduction and capture `DEBUG` state before and after the required refresh. Then isolate whether the stale component is the content script, page DOM, service-worker state, or message listener registration.

### Required regression coverage

- reproduce the current `Ctrl+R` dependency in an automated browser scenario;
- after the eventual repair, equivalent state/reload transitions converge without manual page refresh;
- existing restart, event replay and stale-content auto-refresh tests remain green.

### Closure criteria

The issue is closed only when the same live transition that currently needs `Ctrl+R` converges automatically and a regression test covers the exact trigger.

---

## New bug template

```text
## BUG-NNN — short title

Status: Open
Priority: P0/P1/P2/P3
First confirmed: YYYY-MM-DD
Area: ...

### Symptom
...

### Evidence / reproduction
...

### Impact
...

### Planned repair
...

### Required regression coverage
...

### Closure criteria
...
```
