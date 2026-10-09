# Anonymous public agent-control status — no-Bridge (draft)

This opt-in alternative to the credentialed status-github command uses
**only anonymous GitHub GET requests** against the fixed public repository
MichalMatu/local-agent. This is not a new authority source.

## Example

Independently determine an agent-control commit, exact tested source
commit, canonical binding, work branch and scoped task prefix. Then run:

```sh
python -m scripts.no_bridge_manual status-github \
  --task-id-prefix local-agent-m8-pr253 \
  --pinned-control-sha "<INDEPENDENT_AGENT_CONTROL_SHA>" \
  --pinned-source-sha "<EXACT_TESTED_SOURCE_SHA>" \
  --agent-binding "<CANONICAL_LOCAL_AGENT_BINDING>" \
  --work-branch "work/<EXPECTED_SOURCE_BRANCH>" \
  --allow-readonly-network --anonymous-public-read
```

Without **both** opt-ins, the anonymous mode performs no network I/O.
Without --anonymous-public-read the existing credentialed mode still
requires LOCAL_AGENT_FABRIC_GITHUB_TOKEN.

## Narrow transport boundary

The anonymous API permits exactly four GET path shapes under a hardcoded,
HTTPS GitHub API repository:

- /git/commits/<40-hex-sha>
- /git/trees/<40-hex-sha>?recursive=1
- /contents/.agent/tasks/<bounded-task-id>.json?ref=<40-hex-sha>
- /contents/.agent/results/<bounded-task-id>.json?ref=<40-hex-sha>

It rejects every other method, request body, path, ref type, query variant
and traversal attempt **before** any network request. It sends no Bearer
token or cookie, never follows redirects and bounds the GitHub response
at 512 KiB with a 15-second request timeout. The normal pinned Git tree
and task/result digest verification and redacted outputs still apply.

The anonymous mode deliberately ignores any token present in the
environment. It cannot access private fabric-data or private user tasks,
and cannot query GitHub paths outside the explicit public allowlist. The
underlying repo/branch is public: task logs or task contents may already
be publicly readable through GitHub itself, but the CLI *only emits*
bounded result metadata, not command text, raw logs or credentials.

This does not authenticate the operator's independently supplied source
pins, turn a GitHub status into trusted Mac execution attestation, retire
legacy Chrome workers, enable ChatGPT Send/ACK or permit retry. GitHub
read availability and rate limits may block this optional path; failure
must remain an unconfirmed/failed read, never permission to act.

Tests cover allowlist preflight, body/method denial, malformed refs,
anonymous headers, redirect rejection, bounded HTTP payloads, HTTP/API
errors, token isolation and default-disabled CLI behavior. Exact-head
Mac smoke and independent review remain necessary. Keep draft.
