# Herdr-inspired reliability audit and operator launch fence

Status: 2026-10-09, implementation branch `work/herdr-operator-launch-fence-20261009`.
Baseline reviewed: Local Agent `main@8bbd46f29ef1aa2a562660c1fd627c98d533df03`; herdr `master@2563803dca97c040beaf3dc3acdcb5a3221b4238`.
This is an architectural comparison of **source code**, not an endorsement of a second scheduler or automatic session resumption. No herdr source is copied.

## Comparison and decisions

| Concern | Herdr source implementation | Existing Local Agent / Fabric | Decision |
| --- | --- | --- | --- |
| Orchestration | `src/api/wait.rs` exposes agent/output/event waits and `src/api/subscriptions.rs` tracks active subscriptions around terminal panes | `local_agent/supervisor/orchestrator.py`, `scheduling.py` and `conversation.py` coordinate bounded workers and optional operator campaigns; `chat_bridge/worker_conversation_fabric.js` mediates reasoning-only child turns | Retain deterministic supervisor and Bridge ownership; consider evidence-only agent wait later |
| Lifecycle | `src/pane/agent_detection.rs` defers ambiguous working-to-idle transitions and avoids repeated screen scans on an unchanged content sequence | Process/claim/result states, timeout watchdogs and separate Fabric terminal-delivery guards give stronger execution evidence; no unified read-only agent lifecycle projection | Adapt conservative, observation-only transitions, never infer completed from idle |
| Events | `src/api/event_hub.rs` uses a bounded 512-event sequence buffer and checked cursor reads that distinguish `Lost` from `Unavailable`; `src/api/subscriptions.rs` distributes changes | Git-backed control/results and browser worker events persist important evidence, with adaptive repository polling in `local_agent/supervisor/policy.py` | Future bounded cursor-driven observer with explicit gap resync; no competing authoritative event log |
| Persistence | `src/persist/writer.rs` snapshots session state with recovery copies; `src/persist/restore.rs` suppresses duplicate agent-session restores | GitHub-first immutable workflow data, daemon claims/run journals, spool, synthetic read-only cold recovery; execution replay is intentionally forbidden | Preserve Local Agent's stricter no-replay rule; add durable **pre-launch fence** for the optional operator path |
| Adapters | `src/integration/registry.rs` enumerates CLI names/installations, `src/agent_resume.rs` validates bounded resume arguments | Explicit Local Agent target bindings and permitted deterministic commands; ChatGPT parent/child transport is not a CLI adapter | Do not import generic CLI spawn or agent resume without separate authorization, process registration and lease review |
| Concurrency | Terminal/PTY actors and per-session pane identities in `src/pty/actor.rs`, `src/session.rs` and terminal runtime files | OS repository/resource flock leases, registered process groups, bounded max four workers, serial fallback | Existing executor isolation is more appropriate; no second scheduler |
| Recovery | `src/remote/restart_policy.rs` checks protocol, detach and health before preserving or restarting a remote server; session restore deduplicates agent ids | Run-journal recovery and receipt reconciliation, no implicit task replay, Bridge delivery uncertainty rules | Fix missing operator launch-attempt evidence without weakening watchdogs or claiming ambiguous success |
| Inter-agent work | `src/api/wait.rs` prompt/wait API and status-filtered subscriptions support coordinating pane-based agents | Fabric supports parallel reasoning-only children, durable request/result contracts, but no authorized recursive executor promotion | Design explicit parent-approved hierarchy/lease/epoch protocol separately. No new child execution authority |

Important qualification: herdr is **not fully push-driven**. Its `src/api/wait.rs:725-755` event wait uses `poll_for_wait` and a timed sleep, and its agent wait reads `events_after` rather than the checked gap API. The useful idea is explicit bounded cursor-loss signaling, not copying the loop or assuming delivery guarantees.

Source links: [herdr event hub](https://github.com/herdrdev/herdr/blob/2563803dca97c040beaf3dc3acdcb5a3221b4238/src/api/event_hub.rs), [agent wait](https://github.com/herdrdev/herdr/blob/2563803dca97c040beaf3dc3acdcb5a3221b4238/src/api/wait.rs), [state detection](https://github.com/herdrdev/herdr/blob/2563803dca97c040beaf3dc3acdcb5a3221b4238/src/pane/agent_detection.rs), [restore](https://github.com/herdrdev/herdr/blob/2563803dca97c040beaf3dc3acdcb5a3221b4238/src/persist/restore.rs), [integration registry](https://github.com/herdrdev/herdr/blob/2563803dca97c040beaf3dc3acdcb5a3221b4238/src/integration/registry.rs), [resume](https://github.com/herdrdev/herdr/blob/2563803dca97c040beaf3dc3acdcb5a3221b4238/src/agent_resume.rs), [restart policy](https://github.com/herdrdev/herdr/blob/2563803dca97c040beaf3dc3acdcb5a3221b4238/src/remote/restart_policy.rs).

## Implemented: single-attempt operator launch fence

Risk: `supervisor/conversation.reap(..., interrupted=True)` intentionally leaves an operator request staged if no result exists; after process/supervisor restart, `start_if_pending()` previously had no durable evidence that the campaign might already have produced browser effects and could spawn it again.

New behavior (only for **already-authorized** optional operator campaigns):

1. A request is staged under existing immutable spool rules.
2. Before `popen_registered`, `operator_queue.reserve_launch_once` exclusively creates and fsyncs `conversation-operator/launches/<request-id>.json`, containing only request ID and digest. A second process cannot claim the same attempt. The marker is **not** an execution grant.
3. On a subsequent observation, any existing marker—including corrupt or incomplete content—blocks automatic spawn. The staged request stays available for **manual reconciliation**. Missing terminal evidence is never interpreted as success or a reason to retry.
4. `operator_observability` exposes `launch_reconciliation_required` when a staged, non-running request is fenced. It does not expose prompt content or paths.
5. An already-published exact remote result still follows existing fresh-origin proof before `discard_spool` clears the marker and spool.

This favors at-most-once browser effects over automatic liveness. A crash after the marker is durable but before actual process spawn also requires reconciliation, by design. The marker alone cannot establish that the process ran, that a child submitted text, or that a task completed. No hierarchical child execution permission, second supervisor, or new GitHub source of truth was added.

## Verification and safety boundaries

Focused cases in `tests/test_conversation_operator_launch_fence.py` cover first launch, competing launches, existing/corrupt/symlink marker, interrupted worker restart, spawn failure, read-only status and cleanup. Existing operator queue, supervisor conversation, and observability tests must also pass, followed by `python scripts/verify.py`.

This branch does not modify `chat_bridge/`, the Fabric Milestone 8 parent-fence contracts or machine agent bindings. GitHub-first private live read/submit ACK, parent fence and successor handoff remain **not authorized for activation**. Keep #209 and #214 separate and review their actual latest heads before integration.

## Next priorities

1. **P0:** Add a manual-only reconciliation API/workflow for fenced campaigns: inspect exact durable result and remote ACK, otherwise record unresolved outcome; any intentional rerun uses a fresh request identity and explicit operator approval. Never delete a fence merely to unblock automation.
2. **P1:** Add observer-only lifecycle projections (`working`, `blocked`, `idle`, `failed`, `completed`, `unknown`) grounded in existing durable claims, results and explicit heartbeats. Never map terminal pane idle directly to task completion.
3. **P1:** Prototype bounded event cursor subscriptions with explicit `history_lost` resync and snapshot comparison. Keep GitHub as coordination truth; rate-limit fallback polling.
4. **P1:** Complete private GitHub-first parent-scoped CAS fence integration, explicit browser ACK/results and cross-device admission in the **existing** Milestone 8 PR chain.
5. **P2:** Specify multilevel reasoning-only delegation edges, immutable operation IDs, cycle/depth limits, approval and explicit handoff epoch; execution remains in the canonical Local Agent boundary.

Branch -> CI -> review -> merge -> release remains unchanged.
