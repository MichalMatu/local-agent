# Manual no-Bridge operator CLI (draft, synthetic review only)

The script scripts/no_bridge_manual.py implements a simple Python-only
offline interface for exchanging the redacted synthetic new-parent handoff
and producing a **non-published** local-agent Mac test task plan.

There is **no Chat Bridge**, browser session, automatic child creation,
terminal ACK, GitHub mutation or daemon restart. The export, inspect and
plan-test commands are entirely offline. A fourth operation requires an
explicit opt-in for GET-only GitHub source verification.
Output is canonical UTF-8 JSON without an extra trailing newline.

## Manual commands

Export only a known-public synthetic recovered observation (the DTO format
returned by the existing pinned recovery reader):

```sh
python -m scripts.no_bridge_manual export \
  --input observed-synthetic.json \
  --pinned-source-sha "<PINNED_GITHUB_COMMIT_SHA>" \
  --destination-parent-url "https://chatgpt.com/c/<NEW_PARENT_ID>" \
  > portable-manifest.json
```

Review an existing portable manifest with an independently verified source
SHA, in the new parent conversation:

```sh
python -m scripts.no_bridge_manual inspect \
  --input portable-manifest.json \
  --pinned-source-sha "<INDEPENDENT_SOURCE_SHA>" \
  --destination-parent-url "https://chatgpt.com/c/<NEW_PARENT_ID>"
```

Plan a bounded read-only source test only with explicit operator review:

```sh
python -m scripts.no_bridge_manual plan-test \
  --job-id m8-source-verify \
  --source-sha "<INDEPENDENT_PR_SHA>" \
  --work-branch "work/<REVIEWED_BRANCH>" \
  --agent-binding "<INDEPENDENTLY_VERIFIED_CANONICAL_BINDING>" \
  --profile core --acknowledge-review > source-plan.json
```

The default plan installs no dependencies. Only when separately approved,
append --approve-isolated-dependencies to request a temporary, pinned,
self-cleaning Python test venv in the candidate plan. This flag merely
**plans** setup: it does not install packages.

## Optional authenticated GET-only source recheck

For a **known-public synthetic** source only, the operator may independently
configure LOCAL_AGENT_FABRIC_GITHUB_TOKEN in the process environment via a
trusted credential source. Never provide a token as a command-line argument,
in a task manifest, in chat, or in a tracked file.

```sh
python -m scripts.no_bridge_manual verify-github \
  --manifest portable-manifest.json \
  --operator-request operator-synthetic.json \
  --child-requests children-synthetic.json \
  --pinned-source-sha "<INDEPENDENT_SOURCE_SHA>" \
  --destination-parent-url "https://chatgpt.com/c/<NEW_PARENT_ID>" \
  --allow-readonly-network
```

This operation delegates to the existing **default-denied** source recheck,
uses the appropriate scoped public/private GitHub API and wraps it in a
GET-only adapter. It emits only a redacted, immutable manual review DTO.
The original source recovery function restricts all inputs to its exact
approved public fixture even on the private-data GitHub repository.
It does not support arbitrary real/private prompts.

A successful source SHA comparison is not independent proof of the GitHub
host or source provenance. Operator-supplied pins and credentials must
originate from a trusted channel, and old browser transports remain unfenced.

## Critical authority restrictions

- Export and inspect check **structure and a caller-supplied pin**, not
  independently authenticated GitHub provenance. A manually carried manifest
  must still be rechecked against GitHub via the default-disabled,
  GET-only verify_manual_handoff_against_github() API before reliance.
- SHA-256 manifest integrity alone does **not** prevent malicious rewrites.
- The task plan is not a publish action. The operator must separately
  verify current task binding, execution-enabled catalog, daemon, exact
  work branch and latest head before intentionally writing a task through
  the existing Local Agent agent-control policy.
- The output cannot authorize ChatGPT Send, child execution, ACK, automatic
  retry, legacy worker retirement or migration of real/private conversations.
- Input files are bounded to 8192 bytes and the JSON shapes are strict;
  source errors deliberately do not echo input data or authentication tokens.
- No source of authority is inferred from a current chat window, browser
  plugin or untrusted file name.

Tests exercise CLI export/inspect round-trip, exact output bytes, denied
private/oversize input, explicit task planning opt-in, separate temporary
dependency approval, default-disabled GitHub verification and redaction of
an explicitly supplied test environment token. Canonical Mac validation and independent
security/integration review remain required. Keep this stacked PR draft.
