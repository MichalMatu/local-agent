# Local Agent / Superchat self-diagnostic — 2026-10-04

Status: parent-led audit complete enough to make bounded repair decisions. No release, production restart, branch cleanup, or active Growclip interruption was performed.

## Baseline verified

- `main` and `v4.20.5` resolve to `bd793d60c3bce4b247deb80a7e2bfc88e8bf4373`.
- Local Agent source/runtime is 4.20.5 and Chat Bridge source is 0.8.1.
- The exact 4.20.5 release SHA had five successful release checks.
- Production completed its natural self-update to 4.20.5 at the exact release SHA.
- The active Growclip worker remained running on the same supervisor; it was not interrupted for this diagnostic.
- Runtime registry validation passed for all nine execution-enabled repositories; `local-agent` remains execution-disabled.

## Audit tracks

### Scheduler / control

No P0/P1 regression found.

The production bounded-parallel supervisor retains a hard maximum of four workers, bounded resource/failure/control backoff, control-repository contention handling, and unrelated-repository admission when a control probe degrades. Global control still drains only when required by the control state.

One operational state defect was found outside scheduler code: the previous parent Superchat `chat-7781d9b9` was still enabled after handoff. Because an expired `next_wake_at` falls back to recurring interval scheduling, the old parent could continue waking in parallel with the new diagnostic parent. The old control was disabled on `chat-bridge-state` with `control_generation=2`; no daemon or Bridge restart was required.

### Bridge / Superchat transport

The transport-only architecture is intact. Conversation scheduling identity is not executable repository authority, and the runtime catalog still marks `local-agent` as execution-disabled.

Current production child delegation is not trustworthy/available yet:

1. Conversation Operator intake is default-disabled and the installed LaunchAgent has no `LOCAL_AGENT_CONVERSATION_OPERATOR_*` configuration.
2. The only implemented MVP child-spawn backend still uses the isolated browser actuator.
3. The known pilot failed before child registration with `chatgpt_login_timeout`.

A concrete defect was isolated in that browser path: `waitForLoginReady()` gated session authentication probing on composer DOM visibility. Therefore a valid authenticated session with a delayed or changed composer could be mislabeled as a login timeout. The later pre-submit `probe` already owns bounded composer stabilization, so authentication readiness does not need that DOM dependency.

Repair candidate: draft PR #135 (`work/selfdiag-child-auth-decouple-20261004`) decouples authentication from composer visibility and adds a synthetic delayed-composer regression. Exact repair SHA `25e817c79086f3962a4cee1b23515a11ebedffd3` completed a full five-job CI run successfully, including `bridge-browser` and `macos-smoke`. It remains intentionally unmerged; CI success is not a release decision.

### Repository routing / bindings

No regression found.

The execution boundary remains fail-closed: runtime registry identity, target repository `.agent/binding.json`, and task `agent_binding` must match. Missing/mismatched task bindings are rejected before claim/execution. Conversation Fabric v3 `repository_ids` are explicitly transformed into reasoning prose and do not grant execution authority.

No LAB:REBIND or DOM-derived repository identity was reintroduced.

### Process lifecycle / resources

No active process leak or restart loop was observed in the fresh bounded host probes. Supervisor, worker, and Conversation Operator subprocess ownership remains under registered process groups and bounded termination/reaping logic.

Maintenance/optimization findings, not release blockers:

- Growclip work workspace is about 2.4 GB and exceeded the bounded file-count scan.
- BloomML work workspace is about 2.6 GB.
- `hardware-lab` control checkout is shallow but currently lacks sparse/partial-clone configuration; its daemon is nevertheless healthy and idle on 4.20.5.
- host data volume was 84% used with about 33 GiB available during the diagnostic.

Recent retained error-log text contains historical Git SSH failures, control-checkout binding dirtiness, and Git timeout entries, but the sampled lines did not carry timestamps. They are evidence for later log/transport hygiene review, not sufficient evidence of a current production regression.

### Docs / observability

Definite documentation drift exists after the 4.20.5 release:

- `CURRENT_HANDOFF.md` still describes 4.20.5 as a cleanup candidate and 4.20.4 as the prior production state.
- `CURRENT_PLAN.md` still describes 4.20.5 as prepared rather than released.
- `GOLDEN_STANDARD.md` still says current production is 4.20.4.
- `OPERATIONS.md` contains an older production-line statement referencing v4.19.10.

Observability gap: normal supervisor/diagnostic status does not expose whether Conversation Operator intake is enabled/configured. This forced the audit to inspect LaunchAgent environment separately.

These are accepted follow-up repairs, but they should remain separate from PR #135 so the child-transport defect stays narrowly reviewable.

## Child delegation decision

The requested multi-child reasoning fan-out was not attempted through the broken browser path. There is currently no simpler supported child backend in the repository, and production Conversation Operator intake is not configured. Per the accepted architecture, the parent continued the audit instead of inventing another execution path or repeating login/Cloudflare/DOM loops.

Children therefore performed no host commands and received no machine execution authority.

## Accepted changes made during this diagnostic

1. Disabled stale previous-parent scheduling state for `chat-7781d9b9` on `chat-bridge-state`.
2. Prepared draft PR #135 for the isolated child authentication/composer coupling defect and verified its exact SHA with a five-job green CI run; no merge/release performed.
3. Used only exact-bound, read-only `host-ops` tasks for host evidence. No Local Agent task was targeted at the execution-disabled `local-agent` repository.
4. Recorded this durable checkpoint in draft PR #136.

## Remaining work before calling child delegation healthy

1. Review/merge of PR #135 requires a separate release decision; this diagnostic does not make one.
2. After deployment, use one bounded child pilot rather than repeating manual login/Cloudflare loops.
3. Only after that pilot passes should Conversation Operator intake be considered trustworthy for parent fan-out.
4. Reconcile current durable release docs and add Conversation Operator configuration state to normal diagnostics/observability.
5. Evaluate workspace/storage-policy maintenance after the self-diagnostic; do not mix it into the child transport repair.

## Current verdict

Core executor/scheduler/routing/process safety boundaries are healthy on 4.20.5. The primary functional blocker discovered by the Superchat self-diagnostic is production child delegation readiness; the browser authentication/composer defect now has a CI-green repair candidate but is not deployed. The primary quality issues are stale release documentation and incomplete operator observability. Parent-level Superchat coordination remains usable while the child path stays disabled.