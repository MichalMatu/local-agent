# M8 no-Bridge security checkpoint — 2026-10-10

Status: **source-only, review-only, browser effects BLOCKED**.

This checkpoint supersedes the source/test status in
`M8_NO_BRIDGE_WINDOW_HANDOFF_20261010.md` (#259) for subsequent
no-Bridge Milestone 8 work. Preserve the older handoff and all failed
receipts; treat every SHA below as an observed pin, not a standing permit.
GitHub and terminal Mac receipts remain the source of truth.

## Guardrails

- Continue only in the operator's existing conversation, using the
  GitHub connector and canonical Mac Local Agent for explicitly scoped
  tests. No Chat Bridge scheduling/delegation, subchats, Codex,
  GitHub Actions or automatic ChatGPT Send/ACK.
- No mutation of `main`, `interface/**`, global agent config,
  installed daemon code, Chrome settings, existing chats or extensions.
  Do not restart Local Agent, claim old-worker retirement or retry an
  ambiguous browser effect.
- Keep all candidate PRs draft/unmerged. Never change a tested branch
  head while an exact-head Mac task is running. English-only for
  machine-generated source/docs/tasks per `AGENTS.md`.
- A GitHub task/result, digest, CAS, synthetic preview, static source
  audit or browser-side JavaScript acknowledgement is **not** physical
  execution attestation or trusted exclusion of offline clients.

## Observed repository and runtime

- `main`: `76865cbc7d92861998e8e33a96193d95c120fe02`,
  unchanged by this track.
- Code checkpoint: PR #265
  `work/m8-chrome-manifest-admission-audit-20261010`, exact tested head
  `7d4572d2632742a0b1d8e39aeff19b298e154a94`.
- Documentation-only successor: this new draft branch, based on the
  exact #265 code commit. The #265 verification is **not** falsely
  relabeled as a test of the documentation successor head.
- Canonical execution binding:
  `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`; this was independently
  matched in `config/agent_bindings.json`, `agent-control/.agent/binding.json`
  and fresh daemon status before exact-head tests.
- Last observed Local Agent status after #265 tests: `idle`,
  `current_task_id=null`, updated
  `2026-10-10T05:00:31.782331+00:00`.
  Refresh this state before any further task.

## Stacked source-only PRs and evidence

| PR | Tested source head | Exact-head Mac evidence |
| --- | --- | --- |
| [#261](https://github.com/MichalMatu/local-agent/pull/261) | `f92bf85243d81de8707ae372e4c6afa6a9391a97` | 51 focused PASS; 1049 full PASS; 83.8% coverage; actual anonymous pinned GET PASS. Reject non-finite exponent overflow/deep JSON errors. |
| [#262](https://github.com/MichalMatu/local-agent/pull/262) | `94c40f322427994f4f73b2af187b83395f09408c` | 58 focused PASS; 1056 full PASS; 83.9% coverage. Explicit-token GET reader has aggregate synchronized session bounds, checked with test fakes; **no live credentialed GET**. |
| [#263](https://github.com/MichalMatu/local-agent/pull/263) | `d84fd131cfb4dbf919d4f047904e4d83c9c05fed` | Initial focused failed with two assertion mismatches; focused v2 60 PASS; full 1058 PASS; 83.9% coverage; real anonymous pinned GET PASS. Debit rejected oversized GET body bytes. |
| [#264](https://github.com/MichalMatu/local-agent/pull/264) | `fe018de5c5c4de1d7ae8a4ffce48de13a9c8fc11` | Focused v5 6 PASS, compile/Ruff and Chrome private activation Node guard PASS. Earlier v1/v2/v4 failed and remain recorded; **no independent full-profile test** on #264. Adds negative source/recursive worker import audit and legacy/offline threat model. |
| [#265](https://github.com/MichalMatu/local-agent/pull/265) | `7d4572d2632742a0b1d8e39aeff19b298e154a94` | Focused 8 PASS, compile/Ruff/Node negative guard PASS, complete log. Full 1066 PASS; 83.9% coverage; clean checkout, exit 0. Pins reviewed Chrome manifest permissions, hosts, injection and duplicate-key boundaries. |

Full-profile output in #261–#263 and #265 may be retained with
`output_truncated=true` despite terminal `done`, exit 0 and
`verify_local --profile full` PASS. Keep the distinction:
**positive execution result, incomplete retained log evidence**, not
independently attested verification.

Durable latest receipts, branch `agent-control`:

- `.agent/results/local-agent-m8-pr265-manifest-audit-focused-20261010-v1.json`
- `.agent/results/local-agent-m8-pr265-full-local-20261010-v1.json`
- `.agent/results/local-agent-m8-pr264-browser-exclusion-focused-20261010-v5.json`
- Prior task IDs and recorded negative attempts are listed in their
  exact PR descriptions and comments.

Previous baseline: #258 1046 full PASS / 83.8% coverage and real
anonymous GET PASS. Preserve #257's initially failed process lifecycle
teardown, separate isolated 11 PASS and second full 1039 PASS.
Do not classify the historical flake as fixed.

## Global old/offline Chrome exclusion — still unproven

The installed legacy DOM driver can directly create ChatGPT tabs,
write to composers and click Send. The GitHub-first path remains
read-only; no private transport/ACK effects were activated.

A client that never adopted the proposed epoch gate can send after
returning from offline; neither its silence nor a GitHub CAS proves its
retirement. The new source/manifest scanner can catch accidental
repository changes, but **always denies browser effect authority**
and cannot inspect physical installed/offline profiles.

Chromium documents that previously injected content scripts may
continue on an already-loaded page even after extension disable or
uninstall, until page navigation/refresh:
https://chromium.googlesource.com/chromium/src/+/main/extensions/docs/security_faq.md

Managed Chrome `ExtensionSettings` supports per-extension
`installation_mode=removed`; this affects only environments where
managed policy is actually enforced. It does not attest to disconnected
unknown devices, and does not undo already injected content scripts:
https://support.google.com/chrome/a/answer/9867568?hl=en-1

Before **any** automated Send/ACK, require a common trusted
effect-time enforcement point that uncooperative old extensions cannot
bypass, OR verifiable removal of every potential old effect source
under controlled browser/session authority. Enumerate profiles,
devices, existing script-bearing tabs, extension identities and offline
return paths. Exercise blocked old client reconnect, page refresh,
restart, lost ACK, ambiguous submission and duplicate prevention.
Obtain independent security/integration review and exact-revision live
browser acceptance; do not infer these from source tests.

The safe present option is **manual lifecycle only**, with GitHub-first
read-only evidence/review and explicit human submission.

## Next steps

1. Re-read `main`, PR heads, daemon, catalog and all exact receipts.
   Do not treat this document's SHA observations as freshness proof.
2. Preserve the #265 tested code SHA and close out documentation as
   draft-only. No immediate need to rerun costly full tests absent code
   changes or new evidence.
3. Plan a finite, auditable Chrome profile/device/session inventory
   and trusted revocation acceptance procedure. Inspect only with
   separate operator approval, especially for destructive browser
   policy, logout, reload or extension-uninstall operations.
4. Independently audit the safety/integration design and negative
   source scanner. Do not label author self-review as independent
   approval.
5. Until effect-time exclusion and independent acceptance exist, keep
   private GitHub-first Send/ACK, automatic retry and takeover **off**.

No merge, global agent modification or production browser mutation is
authorized by this checkpoint.
