# GitHub-first Conversation Fabric — current handoff

**Checkpoint: 2026-10-10. One real private GitHub-first child E2E: PASS.**
This is the active continuation entrypoint for PR #274. The longer historical
Milestone 8 timeline is preserved in Git history; it is not a second runbook.
Re-read all refs before writing code, submitting tasks or deciding to merge.

## Source of truth at handoff

| Surface | Verified state |
| --- | --- |
| Public repository | `MichalMatu/local-agent` |
| Production `main` | `f9f73e97a061d5ba590021ddae14b45f705cb7ae`, **not modified** |
| Candidate | `work/fabric-github-first-live-mvp`, observed `940bf803c2469ed2ae078060de4e5305dc0aa323` |
| Pull request | [#274](https://github.com/MichalMatu/local-agent/pull/274), OPEN/DRAFT, targets `main`, **not merged** |
| Control branches | `agent-control`, `chat-bridge-state`, `operator-control` — operational, not disposable |
| Private transport | `MichalMatu/local-agent-fabric-private:fabric-data` |
| Local Agent | `4.20.6`, idle at last read, canonical `agent_binding=2180d453-1357-4fbc-be1a-e1e5b8fbb10a` |
| Candidate Chat Bridge | `0.8.18`, content protocol `26`; installed in operator's existing authenticated Chrome |
| Operator Chrome | Same existing profile; no second Chrome instance or profile |

**Important:** The candidate HEAD may advance through further documentation
edits. The SHA above describes the independently checked functional checkpoint,
not a checkout pin for future work. The installed extension is not automatically
updated when source code changes; distinguish source, staged files and actual
reloaded browser code.

## What was actually accepted

The **second**, operator-launched single-child private GitHub-first trial
completed in the existing Chrome profile:

- Parent: `https://chatgpt.com/c/6aca323f-ec58-83eb-bb3f-5be611bc7770`.
- Private dispatch: `fabric-a8a79801818a745c63c9e3674597522e`.
- Child request: `fabric-live-verify-02`.
- Child: `https://chatgpt.com/c/6aca5422-3a90-83ed-b2e1-3baaf114533f`.
- Browser assistant reply: `FABRIC_PRIVATE_E2E_V2_OK | value=42 | role=verification`,
  followed by the exact ASCII completion marker.
- **Independently verified on private GitHub:** the immutable `claim`, browser
  `ack` and terminal `result` files exist under
  `projects/local-agent/workflows/workflow-001/receipts/<dispatch-id>/`.
  All three carry the same child ID and transaction; ACK and result agree on the
  exact child URL; result includes the expected answer and assistant identity.
  The private result stores answer text without the footer (intentional).

The first dispatch
`fabric-13795c4be8cc6d08c8cda3120d6efebd` **did not pass**:
its private `claim` exists, but ACK/result are absent. The original page
reported no local page-level Send claim, no composer and no user messages,
but that is not authoritative proof that browser Send never occurred. Its
`submission_unknown` state is preserved; **never retry that dispatch** or
erase the claim to make a test pass.

This checkpoint proves one-child **private GitHub-first
claim → browser Send → ACK → stable terminal result**. It does **not** prove
multi-child parent aggregation, cold Chrome/MV3 restart recovery, global
cross-device exclusion, automatic successor Superchat, or merging safety.

## Implemented and tested in the candidate

- Indexed, validated private OperatorRequest/ChildRequest ingestion through the
  canonical Mac Local Agent, immutable private dispatch publication and
  pinned private reads.
- Browser worker: operator-only launch, GitHub-managed exact parent admission,
  unique private claim, existing authenticated Chrome UI driver,
  durable unknown-Send fence, private ACK/result and no automatic Send replay.
- Popup: separate persistent dispatch-ID save, **session-only** scoped token,
  masked four-character suffix, remembered Advanced settings, explicit status.
  Token never belongs in public GitHub, page DOM, task logs or documentation.
- `0.8.17`: pre-submit fresh-page/composer readiness gate: when ChatGPT loads
  slowly, stay in `tab_ready` and retry readiness only; never silently
  re-arm a recorded ambiguous Send.
- `0.8.18`: operator-only abandon action can fence a genuine
  `submission_unknown` trial without resending and excludes that dispatch
  ID from future launches. The existing successful second trial is not
  abandonable. A **later candidate-only popup fix** disables the button
  outside `submission_unknown` and preserves actual status on rejection;
  do not assume this later JS is already loaded in Chrome.

Evidence on `agent-control`: `local-agent-fabric-abandon-0818-final-gates-20261010-v2`
passed the full Bridge suite; `local-agent-fabric-popup-phase-guard-20261010-v2`
passed the final popup/worker checks. Earlier isolated Chromium tests also
passed, but those are separate from the real Chrome trial. PR #274 includes
live-evidence comments. GitHub Actions are manual-only due to operator cost
constraints; **do not dispatch Actions without approval**.

## Non-negotiable continuation rules

1. Read `AGENTS.md`, this handoff, `GITHUB_FIRST_MVP_TRIAL.md`,
   `TARGET_PRODUCT_ARCHITECTURE.md` and the candidate PR diff/tests.
2. Re-read live `main`, candidate HEAD, open PRs, private `fabric-data`
   and `.agent/status/daemon.json` on `agent-control`.
3. Work only on `work/fabric-github-first-live-mvp` until the operator
   chooses otherwise. Never touch or merge `main` as housekeeping.
4. All **executable** work goes through a fresh exact source-head Local Agent
   `.agent/tasks` job with the actual target's **canonical agent binding**.
   GitHub code edits may be made directly on the candidate branch.
5. Do not restart Local Agent or Chrome, reload the extension, resend an
   uncertain bootstrap, close owned child tabs, clear storage, or change the
   global Master state without specific operator approval.
6. Keep private prompts, GitHub tokens and unredacted child records in the
   private repository. Public tasks/results/PR comments carry opaque IDs and
   bounded non-sensitive evidence only.

## Next accepted increment

Build and independently test **multi-child GitHub-first dispatch** in small
steps, without changing the currently accepted one-child live path:

1. Audit private schema/dispatch/receipt contracts and propose bounded
   2-child admission, ownership and parent aggregation rules. Preserve the
   ability to test each child independently; avoid global Send/replay races.
2. Implement regression tests for distinct child identities, duplicate claim
   protection, per-child ACK/result, out-of-order completion, partial failure,
   and restarted MV3 worker resumption.
3. Run exact-HEAD Mac Bridge/Python tests and isolated MV3 browser smoke
   through canonical Local Agent. Record pass/fail with durable task IDs.
4. Request a **separate supervised real Chrome acceptance** for two children
   after code gates pass; user must approve any extension reload.
5. Test MV3 restart/interruption and finally cross-device global parent
   exclusivity. Do not infer these from the one-child E2E.

Keep PR #274 draft until the operator approves the next merge gate; no
automatic rollout of GitHub-first across conversations.

## Branch and documentation hygiene

At this checkpoint exactly five public branches existed: `main`,
`agent-control`, `chat-bridge-state`, `operator-control`, and
`work/fabric-github-first-live-mvp`. **None is redundant or deletable now.**
There was exactly one open PR, #274. Avoid inventing cleanup by deleting
operational refs or the source branch of an active draft.

This concise handoff supersedes older checkpoint prose in its *own prior Git
revisions*. Legacy DOM runbooks remain historical/legacy-specific evidence.
For a new ChatGPT window, use
[GITHUB_FIRST_NEXT_SUPERCHAT_PROMPT.md](GITHUB_FIRST_NEXT_SUPERCHAT_PROMPT.md).
