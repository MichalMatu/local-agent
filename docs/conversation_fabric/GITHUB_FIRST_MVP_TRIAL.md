# Private GitHub-first Conversation Fabric — supervised MVP

**Status (2026-10-10): one real Chrome child E2E PASS.**
This is a *single-child* operator-gated proof, **not** a general production
enablement. The live evidence and next gates are in
[GITHUB_FIRST_CURRENT_HANDOFF.md](GITHUB_FIRST_CURRENT_HANDOFF.md).

## Routing and authority

- Public source: `MichalMatu/local-agent`, candidate
  `work/fabric-github-first-live-mvp`, draft PR #274. `main` unchanged.
- Private coordination: `MichalMatu/local-agent-fabric-private:fabric-data`,
  under `projects/local-agent/workflows/workflow-001/`.
- `requests/index.json` indexes an envelope named
  `requests/<operator-request-id>.json` with OperatorRequest v3 and
  ChildRequest v1 objects. Private request text **never** goes to public
  `agent-control`.
- The trusted canonical Local Agent stages `dispatches/<dispatch-id>.json`
  and updates `dispatches/index.json` atomically after validation.
- The extension writes each private browser receipt to
  `receipts/<dispatch-id>/{claim,ack,result}/<child-request-id>.json`.
- The public `chat-bridge-state` desired-state control is scheduling and
  parent admission state, **not** task-execution authority.
- Each executable Mac task still requires the current canonical target
  `agent_binding` and normal Local Agent admission. Children reason only.

## Operator-controlled one-child test

1. Read `AGENTS.md` and the current handoff. Re-check parent control,
   source SHA, active trial phase and existing receipts first.
2. Publish one valid private request, then stage it with an exact-bound
   Local Agent command (Mac GitHub CLI credential stays on Mac):

   ```sh
   LOCAL_AGENT_GITHUB_FABRIC_WRITE_TOKEN="$(gh auth token)" \
     python3 -m local_agent.conversation.github_fabric_private_live \
     --request-id <operator-request-id> --stage-private
   ```

   The public task contains only the opaque request ID and exact source/binding;
   do **not** log the token or copy the private child prompt into task output.

3. In the existing authenticated Chrome with approved installed Bridge
   **0.8.18**, open Advanced settings, independently **Save dispatch ID** and
   **Save token**. Token requires Contents read/write on the *private* repo;
   it is stored in `chrome.storage.session`, not persistent local storage.
   Popup shows only its last four characters. Do not paste it in ChatGPT.
4. With the GitHub-managed parent and Master enabled, press
   **Launch one child once**. The worker creates a unique private `claim`,
   checks the first fresh page and its editor, submits the bootstrap through
   the existing Chrome DOM driver, then records browser `ACK` and `result`
   when it observes the exact child completion proof.
5. Check **Check trial**, then independently verify matching child identity,
   transaction and URL in all three private receipts. Never infer a PASS from
   the popup or a screenshot alone.

**No blind replay.** If the trial reaches `submission_unknown`, preserve
the record and original claim. Do not click Launch again, remove the claim or
reset extension storage. Operator-only **Abandon failed trial (no retry)**
permanently excludes an unresolved dispatch; it is not allowed once the active
trial moves to another phase. The phase-guard popup improvement is in the
candidate source but may not be present in the installed unpacked extension
until a separately approved reload.

## Verified live evidence

**Second trial: PASS** (existing operator Chrome):

- Dispatch: `fabric-a8a79801818a745c63c9e3674597522e`.
- Child: `fabric-live-verify-02`.
- Parent: `https://chatgpt.com/c/6aca323f-ec58-83eb-bb3f-5be611bc7770`.
- Child URL: `https://chatgpt.com/c/6aca5422-3a90-83ed-b2e1-3baaf114533f`.
- Assistant: `FABRIC_PRIVATE_E2E_V2_OK | value=42 | role=verification`
  plus expected final completion marker in the browser.
- Independent private Github read: **claim PASS, ACK PASS, result PASS**,
  identical transaction and child request ID, exact ACK/result child URL.
  The result payload stores bounded assistant answer **without the marker**.

**First trial: unresolved, NOT PASS.**
Dispatch `fabric-13795c4be8cc6d08c8cda3120d6efebd` has a claim
but no ACK/result. It was not retried. The initial Chrome page remained on
`/`, with no page-local Send claim or user message in the operator's read-only
diagnostic. Never use that absence alone as global proof of no Send.

## Outstanding before wider activation

- Multi-child private admission, per-child ACK/result and parent aggregation.
- Real MV3 restart/cold browser recovery with durable no-replay.
- Cross-device and legacy-driver **global** parent ownership/epoch fencing,
  revocation and security review.
- Explicit operator approval for every further installed extension reload,
  real Chrome test or draft-PR merge. No hosted GitHub Actions without approval.

The accepted live test is **one child only**; isolated Chromium and Node
simulations are additional regression evidence, not substitutes for it.
