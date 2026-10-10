# Private GitHub-first Conversation Fabric — MVP trial

Status: source implementation only. **Live Chrome trial has not been executed.**
The installed production Bridge must not be reloaded without operator approval.
Legacy DOM campaigns remain available and unmodified on `main`.

## Fixed routing

- Private GitHub source: `MichalMatu/local-agent-fabric-private`, branch `fabric-data`.
- Private request inbox: `projects/local-agent/workflows/workflow-001/requests/`.
- Private dispatch index: `projects/local-agent/workflows/workflow-001/dispatches/index.json`.
- Private ACK/terminal evidence: `projects/local-agent/workflows/workflow-001/receipts/<dispatch-id>/{claim,ack,result}/<child-request-id>.json`.
- The public `MichalMatu/local-agent` branch `agent-control` may carry only opaque request IDs and ordinary task metadata; never private prompts or tokens.
- One operator-armed child only. No autonomous activation, secondary Chrome, or hosted GitHub Actions.

## 1. Superchat → private ChildRequest

The Superchat writes one bounded, validated JSON envelope to the private request
inbox under the operator request ID, and indexes that ID in the sorted
`requests/index.json` array:

```json
{"schema_version":1,"request_ids":["operator-request-001"]}
```

Envelope path: `requests/operator-request-001.json`; fields:

```json
{
  "schema_version": 1,
  "operator_request": "<full existing OperatorRequest v3 object>",
  "child_requests": ["<full existing ChildRequest v1 object>"]
}
```

The strings above are explanatory placeholders, not runnable requests.
The trusted validator requires actual objects, a valid parent ChatGPT conversation
URL, a canonical repository binding, consistent workflow/node/role and a valid
bootstrap. The trial requires exactly one child. Never include a token.

## 2. Local Agent → immutable private dispatch

Submit an ordinary `agent-control` task on the canonical Local Agent binding
and candidate branch, with a command equivalent to the following on the trusted
Mac. Only the opaque private request ID appears in the public task:

```sh
set -euo pipefail
LOCAL_AGENT_GITHUB_FABRIC_WRITE_TOKEN="$(gh auth token)" \
  python -m local_agent.conversation.github_fabric_private_live \
    --request-id operator-request-001 --stage-private
```

Requires the Mac's existing GitHub CLI identity to have read/write access to
the private repo. Do **not** print, log or store the token in a public task.
The publisher performs pinned private reads, semantic validation, immutable
request-ID collision checks, and an atomic non-forced dispatch/index GitHub
commit. It emits only a dispatch ID, status and private GitHub commit SHA.

## 3. Operator-armed Chat Bridge → browser

After an explicitly approved update to Bridge **0.8.16**, open its popup,
expand Advanced Settings and enter the exact `fabric-...` dispatch ID and
a scoped private-repository Contents read/write token. Press **Save dispatch
ID** and **Save token** independently. The ID persists in extension-local
storage; the token stays only in Chrome session storage and its last four
characters confirm that it was saved. Advanced settings reopen in their previous
expanded/collapsed state. Once both inputs show saved, press **Launch one child**
exactly once. Do not paste this token into ChatGPT or GitHub public files. A Chrome or extension restart clears the token, so re-enter it after a restart.

Before a browser effect, the worker requires a managed GitHub-backed parent,
no unresolved legacy parent campaign, an indexed SHA-pinned private dispatch,
and a unique private GitHub child claim. It persists a local parent-mode fence
before claim/Send and persists `submission_unknown` before attempting UI Send.
The worker will never replay a potentially submitted message. Results are
detected via the existing child completion proof and published to private
GitHub; the parent reads them directly through GitHub Connector.

**Check trial** reads safe status. **Rollback completed trial** retires the
local GitHub-first parent fence only after the terminal result has been durably
published. In ambiguous or unfinished states, recovery is read-only and
rollback is denied.

## Remaining live acceptance

1. Obtain operator approval to update/reload the existing extension in its
   existing authenticated Chrome; no second browser/profile.
2. Stage a real, one-child private request from the actual Superchat parent.
3. Confirm private claim → UI tab → Send → private ACK → child result → private
   result → Superchat GitHub read; verify replay issues no second Send.
4. Only after a successful live trial, test two children and MV3 restart
   recovery. The first trial is not a substitute for those tests.

Local mocked-UI and isolated Chromium passes must never be described as a
real GitHub-first Chrome E2E. Cross-device legacy-driver exclusion is not
established by the local parent fence; leave broader rollout disabled.
