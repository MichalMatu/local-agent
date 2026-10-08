# Checkpoint — Chat Bridge 0.8.13 live Conversation Fabric acceptance

Date: 2026-10-08. Repository: `MichalMatu/local-agent`.

## Exact source and evidence

- Baseline: `main@a7731b059fdab9b17ac8aa51df370814c101c257` (before this documentation checkpoint).
- Chrome extension: **Chat Bridge 0.8.13**, shared content protocol **v26**, assistant guard **v8**.
- PR [#190](https://github.com/MichalMatu/local-agent/pull/190): visibility of disabled-parent admission rejections.
- PR [#191](https://github.com/MichalMatu/local-agent/pull/191): ASCII child completion token plus exact legacy-token compatibility.
- PR [#192](https://github.com/MichalMatu/local-agent/pull/192): manifest 0.8.13 / content protocol v26. Six canonical CI jobs succeeded (workflow [37781178079](https://github.com/MichalMatu/local-agent/actions/runs/37781178079)).

## Normal Chrome acceptance — observed, not inferred from CI

The operator reported reloading the installed extension and parent tab, with the managed parent and Master enabled, and seeing version **0.8.13**.

1. **Single-child E2E: PASS.** Campaign `cf-a9f08cda8905ab33`, child `bridge-0813-e2e-01` (`verification`), returned `BRIDGE_0813_SMOKE_OK | product=323 | letters=6`. Bridge reported `completed`, stable result capture and owned-tab cleanup.
2. **Three-child parallel E2E: PASS.** Campaign `cf-df084c77d84a5929` reported `completed`, stable capture and owned-tab cleanup for all three children, with no reported child failure:
   - `bridge-0813-parallel-research`: `PARALLEL_RESEARCH_OK | value=391 | role=research`
   - `bridge-0813-parallel-verification`: `PARALLEL_VERIFICATION_OK | value=12 | role=verification`
   - `bridge-0813-parallel-integration`: `PARALLEL_INTEGRATION_OK | value=6 | role=integration`
3. **Earlier failure — closed, not replayed.** Campaign `cf-0c2fd2d492856bc8` produced `spawn_tab_unavailable` after the operator manually closed the child tab. The earlier child response lacked the exact legacy completion footer. Neither event is evidence that the new 0.8.13 ASCII footer failed. Do not replay that task or infer captured results without explicit vault inspection.

These are **operator-provided live browser observations**. The CI browser suite additionally tests lifecycle, exact claims, result capture and worker recovery using a controlled Chromium harness; it is not a substitute for a live browser restart experiment.

## Accepted boundaries

- Only an explicitly controlled managed parent can delegate 1–4 reasoning-only children.
- Child bootstrap and result adoption require exact identity and terminal completion proof; missing/truncated evidence remains pending. The new ASCII `LOCAL_AGENT_CF_CHILD_COMPLETE:<fingerprint>:<child-id>:<checksum>` footer avoids rich-text angle brackets; old fully formed markers remain readable.
- Stable captured results are stored before cleanup in durable campaign state and the bounded Result Vault.
- Owned-tab cleanup is identity-bound. Closing a child tab manually before capture can fail its work; never auto-resubmit.
- GitHub `conversation_controls` governs remote pacing; Chrome Bridge owns child tabs; executable repository tasks require canonical Local Agent catalog admission and exact target `agent_binding`.

## Not yet accepted live

- Controlled MV3 service-worker/extension reload **during** an active child campaign, followed by exact-claim recovery, result capture, cleanup and no bootstrap replay.
- Browser interruption or ambiguous submission during a live campaign, with no duplicate child request.
- Two **successive** completed live campaigns have occurred; however, the active-campaign reload test remains separate. Optional remote Operator telemetry activation is not verified.
- Neither a successful browser CI nor this checkpoint proves the installed Local Agent daemon currently runs the same `main` revision. Check live `self_revision` before machine execution.

## Next safe test

In the installed Chrome 0.8.13 parent, initiate a **new** bounded delegation only when the operator is ready. While the children are active, reload the extension/service worker once under controlled conditions (keep child tabs open), then verify unique child bootstrap submission, exact tab recovery, stable results, cleanup and no stale terminal replay. If identity is ambiguous, stop and retain evidence. Do **not** restart or replay the old failed campaign.

## Work-branch audit (2026-10-08)

There were **15** `work/*` branches and **no open PRs** before this checkpoint. Of those, **13** have a corresponding merged PR:

| Branch | Merged PR |
| --- | --- |
| `work/bridge-0813-completion-protocol-v26` | #192 |
| `work/cf-ascii-child-completion-marker` | #191 |
| `work/cf-unmanaged-intake-diagnostics` | #190 |
| `work/phase-c-artifact-deploy-projection-v1` | #189 |
| `work/cf-browser-smoke-recovery-race` | #188 |
| `work/cf-delegation-diagnostics-clean` | #187 |
| `work/cf-spawn-phase-model-v2` | #186 |
| `work/cf-github-first-v2-clean` | #183 |
| `work/tool-runtime-adb-transfer-v1` | #184 |
| `work/cf-parent-composer-isolation-v1` | #182 |
| `work/phase-c-debug-read-v1` | #181 |
| `work/phase-c-migration-wave-2` | #180 |
| `work/phase-c-tool-runtime-v1` | #179 |

`work/cf-delegation-diagnostics-v1` belongs to closed, **unmerged** PR #185; its replacement PR #187 was merged. `work/cf-github-control-v2` had **no associated open/closed PR** in the recent PR audit: preserve it until its unique work has been reviewed.

The connected GitHub tool set does not offer branch-ref deletion. **No branches were deleted by this checkpoint.** When authorized GitHub branch deletion is available, delete only exact verified merged-PR heads above; consider the superseded #185 branch separately after confirming no unique work, and preserve unverified branches. Never delete `main`, `agent-control`, `chat-bridge-state` or `operator-control`. Remove this checkpoint's work branch after its PR is merged.

## Navigation

Current operations: `docs/OPERATIONS.md`. Current Fabric contract and next acceptance: `docs/conversation_fabric/CURRENT_PLAN.md`. Active implementation: `docs/CURRENT_HANDOFF.md` and `docs/DEVELOPMENT_PLAN.md`. Historical isolated-profile Stage 8 handoffs are evidence only.
