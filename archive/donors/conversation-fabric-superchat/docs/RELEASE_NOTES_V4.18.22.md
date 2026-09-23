# Local Agent 4.18.22

## Summary

Allow ChatGPT to manage Chat Bridge repository binding explicitly, while preserving exact repository-id validation and per-wake hard-binding semantics.

This release also fixes Bridge-local reload controls so `RELOAD=BRIDGE` and `RELOAD=CONTENT` remain usable during bootstrap/rebind transitions instead of being rejected by ordinary binding-freshness guards.

## Assistant binding controls

The assistant may now emit exact final-line controls:

- `[LAB:ADD=<repository-id>]` — bind and enable an unconfigured conversation;
- `[LAB:REBIND=<repository-id>]` — explicitly switch a configured conversation to one exact runtime-catalog repository;
- `[LAB:REMOVE]` — remove the current conversation from Bridge configuration.

Repository ids are validated against the runtime catalog. The Bridge does not infer repository identity from prose. Rebind creates a fresh binding revision/bootstrap boundary before work may continue under the new repository.

User-authored `LAB:OP:*` controls remain available as operator equivalents.

## Reload robustness

Assistant `RELOAD=BRIDGE` and `RELOAD=CONTENT` are Bridge-local maintenance actions and no longer depend on ordinary binding-revision/bootstrap freshness. Sender URL, extension identity, assistant baseline and dedupe checks remain enforced.

## Content protocol

- Local Agent: `4.18.22`
- Chat Bridge: `0.5.9`
- Content protocol: `v7`

The protocol bump is intentional because the content-side control parser changed. Existing tabs must therefore be detected as stale and reinjected after the new service worker starts instead of silently keeping the v6 parser.

## Regression coverage

Tests cover assistant add/rebind/remove, persistent dedupe after removal, exact runtime-catalog selection, reload during pending bootstrap, parser rejection of invalid repository ids, and preservation of the operator namespace.

The global Bridge Master switch and Local Agent emergency-disable marker remain separate manual kill switches. Branch selection remains task-scoped through `work_branch`; this release does not restore any branch-to-conversation coupling.
