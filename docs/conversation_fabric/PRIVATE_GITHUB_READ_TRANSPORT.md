# Future private GitHub Fabric read-only transport

Status: **unimported contract prototype; no private repo or production token provisioned**.

The target sensitive data repository name is reserved in code as
`MichalMatu/local-agent-fabric-private`, branch `fabric-data`. The
repository is **not created or configured by this change**. GitHub access
control works at repository level; a private branch in public
`MichalMatu/local-agent` would **not** hide bootstrap text.

`chat_bridge/github_fabric_private_transport.js` is a separate,
default-disabled, **unimported** module. Its tests exclusively inject
a fake network reader with an approved public synthetic dispatch fixture.
It is not imported by the production extension worker, manifest or content
scripts; the currently active Chat Bridge continues using its existing
public, synthetic-only read-only path and DOM production delegation.

## Tested reader contract

- Only `api.github.com`, the single reserved repository and a fixed
  `fabric-data` ref are valid source endpoints. No caller-supplied URL,
  alternate host, branch or repository is followed.
- Caller must explicitly enable the read and supply a syntactically safe,
  read-only token. There is **no** token store, public runtime setting,
  GitHub write credential, child DOM injection or automatic credential
  acquisition. Failed authorization produces no network request.
- Fetches are GET-only with redirects rejected, cookies omitted and
  `cache: no-store`. Errors never echo URLs with secrets, token headers
  or response bodies.
- Each response is bounded as bytes arrive; GitHub base64 metadata,
  UTF-8 JSON, paths, sizes and source schema are verified. Responses are
  always read by one immutable commit SHA resolved from the ref first.
- Dispatch, campaign, child bootstrap and first-attempt spawn transaction
  identifiers are rederived with SHA-256 from their corresponding source
  fields. Invalid, mutated or partial evidence fails closed.
- Result contains only the verified read-only dispatch and origin SHA.
  It is **not** an ACK, child-spawn claim or permission to click Send.

## Production prerequisites

1. Explicitly provision the private repository and select an access
   policy. Local Agent needs Contents:write scoped to this repo; the
   authenticated browser reader needs **Contents:read only**, subject
   to revocation and rotation. Never put either token in public runtime,
   logs, page content or child prompts.
2. Establish a protected extension-only credential lifecycle and
   operator-controlled enablement; review Chrome extension host access.
   The current prototype deliberately provides neither capability.
3. Implement a trusted private publisher that verifies child/parent
   workflow admission and results, with record/index CAS and readback.
   Never lift the existing public-fingerprint allowlist.
4. Add parent-mode fencing and one semantic-node authority that excludes
   old DOM dispatch. No claim or seen fingerprint grants execution alone.
5. Add genuine consumer ACK and trusted terminal-result publication,
   restart/failure injection, independently verified cross-device read
   and real-Chrome acceptance before enabling any private child spawn.

Tests use only synthetic text and mocked GitHub responses. They do **not**
prove real private repository permissions or credential handling.
