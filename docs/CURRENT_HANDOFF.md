# Current handoff — operator-visible Conversation Fabric intake accepted

Date: 2026-10-03
Status: the end-to-end Conversation Fabric MVP and the GitHub-backed operator-visible intake are accepted on the canonical development line. The next decision is controlled production rollout/release, not another hidden lifecycle or intake milestone.

## Read this first

Repository state, durable docs and fresh `host-ops` evidence outrank chat memory.

Read in this order:

1. `AGENTS.md`
2. this file
3. `docs/conversation_fabric/CURRENT_PLAN.md`
4. `docs/DEVELOPMENT_PLAN.md`
5. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`
6. `docs/OPERATIONS.md`

## Authoritative repository state

Production remains unchanged and clean:

- `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent: v4.19.12
- Chat Bridge: 0.6.2
- production checkout: `/Users/michal/local-agent`
- production Chrome profile: `/Users/michal/Library/Application Support/Google/Chrome`

Conversation Fabric development:

- canonical branch: `develop/conversation-fabric`
- accepted operator-visible CODE: `37e480d3b36a5c15db89c944ef46f01225a4b379`
- commit: `Add operator-visible Conversation Fabric intake`
- tree: `02910eadc544a87cd9fcb5287abd26e1a05d7688`
- exact-SHA clean CI: `37085317848`
- CI result: all five jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`
- accepted underlying end-to-end MVP CODE: `93494b2a99162eef5bcf44caae087b71459233b4`
- DEV checkout: `/Users/michal/local-agent-dev`

Documentation-only commits may advance `develop/conversation-fabric` beyond accepted CODE `37e480d...`. Always distinguish accepted runtime CODE from a later docs-only head.

## Accepted operator-visible slice

The durable operator boundary is now:

```text
Operator Chat / Superchat
  -> .agent/conversation/requests/<request-id>.json
  -> Local Agent validates and stages one immutable bounded request
  -> existing run_mvp_campaign() owns the complete child lifecycle
  -> bounded operator result
  -> .agent/conversation/results/<request-id>.json
  -> Operator Chat reads/synthesizes the result
```

The request carries operator intent only: schema version, immutable request id, workflow id, canonical parent conversation URL, and one to four bounded children with `request_id`, `node_id`, `role`, `summary`, and `paths`. It does not duplicate `.agent/tasks`, repository execution contracts, or child lifecycle state.

The result is a bounded operator snapshot with overall state, immutable request digest, child counts, and per-child state, bounded summary/error, canonical child URL and evidence digest. Internal browser transactions, retry counters and detailed lifecycle records remain diagnostic evidence rather than the default operator surface.

Accepted properties include:

- the existing MVP lifecycle is reused rather than reimplemented;
- `.agent/tasks` remains the executable repository-work contract and is unchanged;
- no MCP or second scheduler/control transport was added;
- supervisor intake is optional and default-disabled without explicit Conversation Fabric runtime configuration;
- browser campaigns run outside repository/resource execution leases and strip inherited lease descriptors;
- active campaigns block full control/self-update service while bounded safety probing/disable remains available;
- interrupted/disabled campaigns preserve staged authority for recovery instead of inventing a second request;
- terminal results are durable locally before publication;
- same-ID request mutation is fail-closed;
- result publication revalidates immutable request identity after pull/rebase and before push;
- spool deletion requires a fresh origin fetch plus exact remote proof of both the request and result;
- `--once`, including disabled mode, cannot silently exit while a terminal operator result still needs publication.

## Acceptance evidence

Final local gate on the accepted tree:

- compile: passed
- Ruff: passed
- 121 focused/integration tests: passed
- 6 package-layout tests: passed

Final independent review of the last publication boundary returned `OPERATOR_FINAL_FRESH_ORIGIN_OK`. Earlier delegated reviews found real recovery/scheduler defects; all reported HIGH/MEDIUM findings were fixed before acceptance.

Clean exact-SHA CI:

- run: `37085317848`
- SHA: `37e480d3b36a5c15db89c944ef46f01225a4b379`
- result: 5/5 green

Clean live operator proof:

- request: `operator-clean-final-request-20261003-v1`
- workflow: `operator-clean-final-workflow-20261003-v1`
- request digest: `sha256:cf6bc270a6dd0ca837acd0a98a16d48d2a7559efcc6cd60ea869aba72295f93a`
- child: `https://chatgpt.com/c/6ac057fc-b140-83ed-b74f-61f1b8de94d7`
- child evidence: `sha256:c32cdffcc9519b9df162a5e501f223fa9396adfb09dc4a73a27aa86d93a879a8`
- operator state: `completed`
- children: 1 total / 1 completed / 0 failed / 0 waiting
- result: `OPERATOR_CLEAN_FINAL_OK 37e480d3b36a5c15db89c944ef46f01225a4b379`
- production mutation: none

## Completed milestone ledger

- Stage 8 automatic child proof: `93fb65204db03c54d0080803d26266f3c06d777e`, CI `37022787748`
- durable terminal records: `a16918d32bc366dbc9d8a8793669baa214d13620`, CI `37036591713`
- durable adoption/retirement: `e76dc4a114f750cc0beabdbb2ad626d41ff2e986`, CI `37054505079`
- restart/recovery boundary proofs: `2557f9477ff34ebb5b8502a15747e5d78f29bd5a`, CI `37056289262`
- first-class manual child lifecycle: `78f72819c2e7d60e0cae4599f8c24976cb0ce2a4`, CI `37062617205`
- end-to-end Conversation Fabric MVP: `93494b2a99162eef5bcf44caae087b71459233b4`, CI `37076387941`
- operator-visible GitHub intake: `37e480d3b36a5c15db89c944ef46f01225a4b379`, CI `37085317848`

## Current priority

Do not start another hidden lifecycle or operator-intake milestone merely because one is available. The next useful step is a controlled production rollout/release decision. Production `main` stays unchanged until the user explicitly chooses release.

Before any release, inspect the repository's current version/changelog/release procedure, decide the exact runtime configuration and rollout order for the default-disabled Conversation Fabric operator intake, verify production safety/rollback boundaries, and require exact release-candidate CI. Enable operator intake only through deliberate configuration after matching code is installed.

## Non-negotiable invariants

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- ChatGPT conversations remain the reasoning layer.
- Chat Bridge remains a bounded browser actuator, not workflow authority.
- child chats do not receive independent machine execution authority.
- browser DOM is transport evidence, not durable scheduler state.
- no blind replay after a potentially submitted ambiguous effect.
- no production Chrome-profile mutation.
- no production `main` mutation without a separate explicit release decision.
- do not use `chat-bridge-state` or `operator-control` as development branches.
- machine-generated source, tests, docs, prompts, task metadata, logs and commit messages remain English-only.
