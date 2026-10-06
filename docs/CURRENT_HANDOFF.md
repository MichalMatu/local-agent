# Current handoff — browser-native Conversation Fabric

Date: 2026-10-07

Status: Local Agent remains on release line `v4.20.6`. The current post-release source candidate uses Chat Bridge `0.8.11` and browser-native Conversation Fabric inside the operator's already authenticated primary Chrome session. The old isolated-profile/Playwright production assumption is retired.

Stable source rollback anchor: `main@59c5d699bc32283ebb98fc026f76128ec9db6d2a`. The current verification and branch-hygiene record is `docs/CHECKPOINT_2026-10-06_SEQUENTIAL_HARDENING_BASELINE.md`; the earlier `docs/CHECKPOINT_2026-10-06_STABLE_MAIN.md` remains historical evidence.

## Current focus

Single-goal Superchat acceptance, lifecycle/recovery, operator observability, corrective-intent dedupe and production-path test-architecture hardening are complete in current source. The sequential delegation-cycle source closeout now includes a production-shaped second-campaign proof in the same parent, covering fresh campaign identity, no inherited results/terminal receipt, exact child cleanup and no replay/mutation of the first campaign.

Host Ops source absorption, live cutover and final machine-target retirement are complete. `local-agent` remains the execution target with binding `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`; exact-head CI #2330 passed for checkpoint `41e653110a4e8d6c88884ff58f34787c774cb0de`. Final preflight `local-agent-final-host-ops-retirement-preflight-20261007-v3` passed, the disabled `host-ops` machine-registry record was removed without reordering any remaining entry, the parallel supervisor accepted a supported restart through canonical first-registry control `growclip`, and `local-agent-post-host-ops-registry-removal-smoke-20261007-v1` passed afterward. The donor repository is now archived/history-only and no longer exists in either the canonical source catalog or machine registry. Archival completed through `local-agent-archive-host-ops-donor-20261007-v2`; `work/cpu-gpu-routing` remains preserved at `901c9c0844beadb8cbe545103b70ba23c7720f7e`. See `docs/CHECKPOINT_2026-10-07_HOST_OPS_RETIREMENT_HANDOFF.md` and `docs/HOST_OPS_ABSORPTION_PLAN.md`.

The operator later disabled the live normal-Chrome Bridge after a field regression repeatedly inserted Conversation Fabric feedback without reliably submitting it and retries began to spam the composer. The source submit path has since been repaired and strengthened, but the post-fix source has not been reloaded or live-accepted. Keep the live Bridge disabled until an explicit operator validation step. Activation of the optional live `operator_status_url` has not been verified and must not be inferred.

## Source of truth

Read fresh repository/runtime evidence in this order:

1. `AGENTS.md`
2. this file
3. `docs/CHECKPOINT_2026-10-07_HOST_OPS_RETIREMENT_HANDOFF.md`
4. `docs/HOST_OPS_ABSORPTION_PLAN.md`
5. `docs/CHECKPOINT_2026-10-06_SEQUENTIAL_HARDENING_BASELINE.md` (historical source/branch snapshot, not the current branch inventory)
6. `docs/CHECKPOINT_2026-10-06_STABLE_MAIN.md` (historical rollback evidence)
7. `docs/GOLDEN_STANDARD.md`
8. `docs/OPERATIONS.md`
9. `docs/AUTONOMOUS_CHAT_LOOP.md`
10. `docs/GITHUB_BRIDGE_CONTROL.md`
11. `docs/conversation_fabric/CURRENT_PLAN.md`

Historical isolated-profile, DEV-lab, self-diagnostic, older checkpoint and release-note documents are evidence only.

## Current authority model

- Chat Bridge conversation identity is transport/scheduling identity only. It never grants repository execution authority.
- Every executable Local Agent task resolves its actual target through the canonical runtime catalog, requires `execution_enabled=true`, and uses the target repository's exact canonical `agent_binding`.
- Registry/control agreement without a matching canonical catalog record fails closed.
- The current canonical catalog enables only `local-agent` for this absorbed Host Ops ownership boundary; self-execution follows the same binding, lease, resource and emergency-control gates as every other target. There is no permanent special-case self-execution ban.
- `local-agent` is provisioned live on the Mac with binding `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`; `local-agent/agent-control` publishes healthy idle status. The standalone `host-ops` identity is absent from both the canonical source catalog and the machine registry.
- The supported `agentd.py` launcher requires the machine repository registry and fails closed when it is absent; it does not fall back to the legacy single-repository executor loop.
- Use direct GitHub edits when an exact repository diff plus CI is sufficient. Use Local Agent only for work that genuinely requires machine-local commands, local builds/tests, devices or host state.
- Conversation Fabric children are reasoning-only. They do not create `.agent/tasks`, run machine commands, mutate repositories or make the final parent execution decision.

## Accepted production browser model

```text
normal authenticated Chrome
  -> managed parent Superchat tab
  -> installed Chat Bridge
  -> LOCAL_AGENT_CF delegate control
  -> existing worker_spawn.js ownership primitives
  -> ordinary reasoning-only child tabs in the same Chrome session
  -> stable child result capture into durable campaign state
  -> owned-tab cleanup
  -> terminal parent feedback at most once
  -> parent synthesis
  -> exact target .agent/tasks only when machine execution is justified
```

Production Conversation Fabric must not launch a second Chrome/Chromium process, maintain a separate ChatGPT profile, copy cookies, use CDP as a second browser-control plane, require another login, or treat Cloudflare recovery as normal orchestration.

Isolation is logical: exact parent conversation, tab id, child URL, spawn transaction, request/bootstrap digests and durable local campaign state. Ambiguous ownership fails closed.

## Conversation Fabric recovery and delivery

- Campaign state is durable in `chrome.storage.local`; every stable child result is additionally copied into a separately retained bounded Result Vault before cleanup or terminal feedback.
- A submitted child survives service-worker restart/reload. Lost session ownership may be reconstructed only from the child page's exact transaction/request/bootstrap/current-URL claim; a reused tab id is never sufficient.
- Pre-submit interruption fails closed. Post-submit routing ambiguity remains recoverable while exact identity can still be proven. Neither state permits automatic child-prompt replay.
- Stable results require the explicit completion marker plus repeated identical observation; successful sibling results survive later child/campaign failures.
- Transient child observation failures remain pending and recoverable rather than becoming permanent child failures.
- A manually closed or explicitly retired child is surfaced as missing coverage when no stable result was captured. Safe failure classes are marked retryable so the parent may intentionally delegate the bounded work again with a new child id; the Bridge never creates that replacement itself.
- The existing GitHub-control alarm normally observes/collects campaigns while the parent and Master are enabled. Explicit `collect` performs bounded recovery for already-submitted children, read-only `inspect` recovers status/vaulted results, and explicit `retire` closes one exact-owned child without replay.
- Terminal feedback uses a durable per-campaign delivery claim before crossing the send boundary. A surviving ambiguous claim suppresses resend after restart, intentionally preferring a possibly missed terminal notification to duplicate terminal delivery.
- A new delegation for a parent is rejected while an older terminal campaign still has undelivered feedback, preventing stale cross-campaign terminal replay.
- Completed/failed campaign cleanup closes only exact owned child tabs.

## Runtime hardening now in `main`

The current source includes the audit repairs that:

- require canonical runtime-catalog admission for workers;
- fail closed when the operational daemon registry is absent;
- reconcile an admitted dedupe receipt from matching durable `result_published` run evidence after a crash, preventing equivalent work from being admitted again solely because the claim disappeared;
- prevent stale Conversation Fabric terminal replay across campaigns and settle nonterminal started/pending feedback without terminal-only ACK retries.

These are production-path invariants, not compatibility hints. New changes must preserve them and add regressions through the real consumer path whenever feasible.

## Task authoring and dedupe

- `python -m local_agent.cli.diagnostics prepare-task` compiles inline drafts using an explicit catalog target and execution profile, then writes the existing immutable task/payload bundle into a publication checkout.
- `validate-task --repository` adds read-only local admission preflight without weakening worker binding checks or taking execution leases.
- Corrective plans use a new task id and higher `dedupe_revision` after completion. Conflicting queued/active intents are reported as `dedupe_intent_conflict`; revisions never bypass an active claim.
- Local Codex invocation policy rejects recognizable invocations but is not a shell sandbox.

## Verification standard

For runtime or Bridge behavior changes:

1. start from current `main`;
2. add a regression reproducing the real production path;
3. run full exact-head CI, including browser and macOS smoke;
4. merge only with green jobs and an expected-head guard;
5. perform bounded live/real-browser acceptance when browser lifecycle/recovery semantics changed;
6. retire only branches proven fully merged.

Children receive bounded source context explicitly; the parent synthesizes results and owns any exact target-bound executable task. No automatic child-prompt replay is permitted after interrupted spawning.
