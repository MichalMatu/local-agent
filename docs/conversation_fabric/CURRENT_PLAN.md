# Conversation Fabric — active legacy DOM/Chrome contract and acceptance


**Scope:** This is the existing browser/DOM `LOCAL_AGENT_CF` production
delegation path, not the future private GitHub-first child-execution path.
For Milestone 8 private project continuity, the active continuation document is
[GitHub-first current handoff](GITHUB_FIRST_CURRENT_HANDOFF.md).
GitHub-first remains default-disabled. The old live Chrome reload experiment
described below is independent of the GitHub-first source-pinned recovery proof.

Legacy DOM source observation: 2026-10-08. Current source: **Chat Bridge 0.8.13 / content protocol v26**.
Live proof and exact source baseline: [2026-10-08 checkpoint](CHECKPOINT_2026-10-08_BRIDGE_0813_LIVE_ACCEPTANCE.md).

## Accepted: single and parallel delegation in normal Chrome

The operator reloaded Bridge 0.8.13 in the authenticated primary Chrome profile, with Master and the managed parent enabled. Two independent campaigns completed and reported automatic exact owned-tab cleanup:

- `cf-a9f08cda8905ab33`: **1/1** verification child, `BRIDGE_0813_SMOKE_OK | product=323 | letters=6`.
- `cf-df084c77d84a5929`: **3/3** parallel children, research `391`, verification `12`, integration `6`.

Both are live field observations, not just simulated CI. The earlier `cf-0c2fd2d492856bc8` attempt failed after the child tab was manually closed; it must not be automatically replayed. Complete details and evidence boundaries are retained in the checkpoint.

## Architecture and authority

```text
managed parent ChatGPT chat (authenticated Chrome)
  -> exact trailing LOCAL_AGENT_CF delegate
  -> Bridge content script + MV3 worker
  -> transaction-owned child tabs (reasoning only)
  -> exact ASCII completion proof + stable observation
  -> durable campaign / Result Vault
  -> exact owned-tab cleanup
  -> terminal parent feedback at most once
  -> parent synthesis
```

- **Bridge/Chrome** owns child-tab spawning, exact transaction/request/bootstrap/current-URL identity and result collection.
- **GitHub conversation_controls** governs remotely managed pacing, not browser child creation. The existing GitHub-control alarm performs routine campaign observation. Manual `collect` only inspects/reconciles already-submitted children.
- **Local Agent** alone owns repository execution admission, scheduling, leases/resources, watchdogs, and `.agent/tasks`. A child or parent chat identity never grants execution authority. Resolve the actual target from the canonical runtime catalog and use the exact target `agent_binding`.
- No production CDP control plane, secondary Chrome profile, cookie migration, browser-to-daemon RPC, or automatic child replacement.

## Control contract

The **last visible content** in the parent's response must be an un-fenced, exact block:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"delegate","children":[{"id":"audit","role":"research","prompt":"A bounded reasoning task with enough context."}]}
LOCAL_AGENT_CF>>>
```

Only registered, enabled parent conversation + Master + exact active top-frame/URL/tab can delegate. Roles: `research`, `implementation`, `verification`, `integration`; children are reasoning-only. A control is not a successful spawn until the worker admits it. The parent waits for actual child feedback, never repeats a pending delegation.

Every new child must end its final answer with the Bridge-provided **plain ASCII footer** `LOCAL_AGENT_CF_CHILD_COMPLETE:<fingerprint>:<child-id>:<checksum>`, as the final non-whitespace line. Legacy exact `<<<LOCAL_AGENT_CF_CHILD_COMPLETE:...>>>` tokens are accepted for previously started campaigns. Missing, partial, or malformed tokens are **not** accepted as success, even when the child appears to have finished writing.

Explicit bounded recovery/inspection (not new work):

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"collect","campaign_id":"cf-..."}
LOCAL_AGENT_CF>>>
```

## Durability / fail-closed rules

- Persist exact transaction identity, child URL and stable captured result **before** owned-tab cleanup; retain result separately in the bounded Result Vault.
- Never resend an ambiguously submitted child bootstrap or auto-create substitute tabs. If a child tab has been manually closed, record a bounded failure instead of guessing.
- After worker restart, adopt only an exact transaction/request/bootstrap/current-child-URL claim; tab ID alone is insufficient.
- Terminal feedback uses durable at-most-once delivery. An ambiguous send is not replayed automatically, and a newer campaign must not inherit the previous one's results/receipt.
- Diagnostic `control_rejected`, `control_worker_rejected`, `control_accepted` and `control_transport_failed` events are **observability**, not delegation/result proof. See [diagnostics](DELEGATION_DIAGNOSTICS.md).

## Remaining live acceptance

**Not yet demonstrated in the operator's real Chrome:** controlled extension/MV3 worker reload **during an active campaign** and verified exact-claim recovery, no child-bootstrap replay, full capture, tab cleanup and no terminal-feedback duplication. Recovery behavior is covered by CI's Chromium harness, but the live interruption test is a separate gate. Optional remote Operator telemetry activation is also unverified.

Recommended next test: one fresh, explicit bounded campaign with two reasoning children; keep child tabs open; trigger one controlled reload while they run; verify ownership, exact one-time bootstrap and completion, and inspect the resulting campaign and popup status. Do not replay the closed old failure.

## Verification and next work

- Source gates: `bridge-browser`, `test`, `coverage`, `python-314`, `macos-smoke`, `absorbed-host-ops` on the **exact PR head**.
- Existing harness: `scripts/conversation_fabric_dom_smoke.cjs` and `scripts/conversation_fabric_browser_smoke.cjs`. No second production browser controller.
- Main development continues in **Milestone 7 Tool Runtime Phase C**, independently of Fabric live acceptance. See [current handoff](../CURRENT_HANDOFF.md).
- Historical Stage 8 isolated-profile / older 0.8.x instructions remain historical evidence, not active operation.
