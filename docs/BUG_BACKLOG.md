# Local Agent bug backlog

This file tracks confirmed or strongly evidenced Local Agent defects that still need engineering work.

`CHANGELOG.md` records changes that have already shipped. This backlog records **known problems and planned fixes before they are completed**.

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
