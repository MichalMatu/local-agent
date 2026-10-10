# GitHub-first Conversation Fabric — new-chat continuation prompt

**Manual handoff, 2026-10-10.** This prompt transfers reasoning context
only: it neither launches children nor binds/schedules a new Chrome conversation.
The new chat must re-read live GitHub evidence and request operator approval
before any browser extension reload or new real Chrome E2E.

## Copy into a new ChatGPT conversation

Continue `MichalMatu/local-agent` GitHub-first Conversation Fabric
development from the **accepted single-child live Chrome checkpoint on
2026-10-10**. Work exclusively on
`work/fabric-github-first-live-mvp` unless I explicitly change the branch.
Do **not** change/merge `main`; do not restart Local Agent or Chrome.
Do not use hosted GitHub Actions or automatic new Superchat promotion.
Use GitHub Connector for repository changes and the exact-bound Local Agent
on `agent-control` for executable Mac tests; work in this chat, with no
automatic subchat delegation unless I explicitly request it.

First read these files **on the current candidate branch**, in order:

1. `AGENTS.md` — repository and execution safety rules.
2. `docs/conversation_fabric/GITHUB_FIRST_CURRENT_HANDOFF.md` — concise
   authoritative state, evidence and next acceptance gates.
3. `docs/conversation_fabric/GITHUB_FIRST_MVP_TRIAL.md` — browser-private
   receipt contract and safe operator instructions.
4. `docs/conversation_fabric/TARGET_PRODUCT_ARCHITECTURE.md` — long-term
   product direction, **not** proof of deployed features.
5. `chat_bridge/README.md` and the exact candidate PR #274 diff/tests.

Re-read the current public `main`/candidate HEADs, private
`MichalMatu/local-agent-fabric-private:fabric-data` receipts,
`chat-bridge-state` managed conversation control, and canonical Local Agent
`.agent/status/daemon.json` plus binding. Current known binding at the
handoff: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`; **verify it afresh**.

### Already confirmed — do not repeat as a setup exercise

One real GitHub-first child succeeded in the operator's existing authenticated
Chrome using installed Bridge 0.8.18:

- Parent: `https://chatgpt.com/c/6aca323f-ec58-83eb-bb3f-5be611bc7770`.
- Private dispatch: `fabric-a8a79801818a745c63c9e3674597522e`.
- Child request: `fabric-live-verify-02`.
- Child URL: `https://chatgpt.com/c/6aca5422-3a90-83ed-b2e1-3baaf114533f`.
- Child answer: `FABRIC_PRIVATE_E2E_V2_OK | value=42 | role=verification`.
- Independently checked private **claim → ACK → result** records, matching
  transaction, child ID, child URL; completion marker visible in real Chrome.

First dispatch `fabric-13795c4be8cc6d08c8cda3120d6efebd` remains
**unresolved with claim only**, not a PASS. Never replay or clear it.
Draft PR #274 remains OPEN and UNMERGED; source `main` untouched.
A candidate-only popup fix disables Abandon outside `submission_unknown`;
do not claim it is installed until separately reloaded and verified.
The public repository had exactly five branches, all needed:
`main`, `agent-control`, `chat-bridge-state`, `operator-control`,
`work/fabric-github-first-live-mvp`. Delete none as housekeeping.

### Your task

Continue with a critical implementation audit and bounded development of
**private multi-child GitHub-first orchestration**: two independent child
requests, exact per-child claims/ACK/results, out-of-order results, partial
failures, parent aggregation and durable no-replay semantics. Design and
test MV3 restart recovery and cross-device/global parent ownership separately.
Do not confuse existing working **legacy DOM multi-child** with new private
GitHub-first multi-child support.

First inspect existing contracts and present a short plan. Implement the
smallest safe increment with regression tests, run exact-HEAD Mac validation
through canonical Local Agent and update the concise handoff. A real second
Chrome trial, extension reload, or merge requires my explicit approval.
No private GitHub token, child prompt or unredacted private receipt may appear
in public PR comments, task outputs or chat transcript.

Report precisely what is PASS, PARTIAL, FAILED or UNVERIFIED. Maintain source
and operational truth, not remembered status.
