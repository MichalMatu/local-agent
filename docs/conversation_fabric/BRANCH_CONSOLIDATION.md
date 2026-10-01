# Branch consolidation record

Status: complete, with the final stale feature donor audited for retirement.

Canonical development branch: `develop/conversation-fabric`.

Production/runtime branches remain separate: `main`, `chat-bridge-state`, `operator-control`.

## Consolidated lineage

The canonical development line preserves the accepted Conversation Fabric history and current target architecture. Historical development/feature branches are donors only and must not become parallel development authorities.

- production base and subsequent production sync points remain preserved in Git history;
- Conversation Fabric implementation history remains on `develop/conversation-fabric`;
- current architecture authority is `TARGET_PRODUCT_ARCHITECTURE.md`;
- current execution/checkpoint authority is `CURRENT_PLAN.md`.

## Active assets preserved

- latest Chat Bridge transient assistant recovery implementation and tests;
- verified `local_agent/workflow/` Execution Fabric core;
- workflow CLI, shared control-Git lock, workflow fixtures and full regression corpus;
- durable result-event outbox;
- notification-only Chrome Native Messaging host/installer + tests;
- Conversation Fabric child lifecycle, campaign ledger and bounded browser-driver work;
- GitHub-only target control/evidence architecture.

Conversation Fabric development remains isolated from production runtime until its explicit release gates pass.

## Deliberately not transplanted as active runtime

Old copies of central Chat Bridge worker/content/delivery files are not made authoritative when they predate later production hardening. Useful behavior must be reimplemented against current owners and current recovery tests rather than merging stale worker files wholesale.

No automatic production Superchat scheduler, unrestricted child-spawn authority, second executor, MCP control plane or direct OpenAI API reasoning loop is enabled by branch consolidation.

## Final stale donor audit: `feat/chat-bridge-attachment-inbox`

The branch was audited before retirement at exact donor head:

`4d0f701ae66215444d39c783ede579d61720a658`

It diverged from the current lines long ago. Relative to current production `main` it contains only five unique commits and is more than one hundred production commits behind; relative to `develop/conversation-fabric` it is also heavily diverged. It must therefore **not** be merged wholesale.

The only unique product idea worth preserving is bounded **attachment ingress** from an ordinary bound ChatGPT conversation. The donor implementation demonstrates these reusable design ideas:

- observe user file-selection, drop and paste events in the bound ChatGPT page;
- authorize ingress only for an exact currently bound conversation;
- validate attachment metadata before any side effect;
- bound one file to 64 MiB and one observed event to at most eight files;
- reject unsafe names/path separators/control characters and sanitize the browser-download filename;
- suppress immediate duplicate observations with a short dedupe window;
- use a browser download as a narrow transport effect rather than granting the page arbitrary local filesystem access;
- keep attachment handling fail-closed when conversation identity or authorization is unavailable.

These are **donor requirements, not accepted active runtime code**. The old implementation depends on a stale Chat Bridge worker/runtime generation and must not be cherry-picked blindly. If attachment ingress becomes useful for Superchat, implement it later as a bounded Browser Driver capability under the canonical GitHub-backed Conversation Fabric authority, with current binding/recovery/security tests.

The branch also contains old MCP/API-era and host-ops integration work from its historical lineage. Those parts are explicitly rejected by `TARGET_PRODUCT_ARCHITECTURE.md` and are not migration candidates.

After this record, `feat/chat-bridge-attachment-inbox` has no remaining architectural authority and is safe to delete as a branch. Its exact donor head above remains the historical reference for any later forensic lookup.

## Donor history

Earlier donor trees were preserved in Git history during the original consolidation and then removed from the active working tree to keep code search, diffs and agent context clean.

Former development branches already superseded/deleted include:

- `feature/chat-bridge-event-wake`;
- `feature/openworker-governance`;
- `feature/conversation-fabric-superchat`;
- `plan/consolidated-development-roadmap`;
- `work/chat-bridge-live-chat-states`;
- `maintenance/transient-recovery-patch`;
- `work/transient-recovery-validation`.

The final stale feature branch to retire is:

- `feat/chat-bridge-attachment-inbox` — audited above; do not merge wholesale.

Production/runtime branches are intentionally **not** cleanup targets:

- `main` — production source of truth;
- `chat-bridge-state` — operational state;
- `operator-control` — operational control;
- `develop/conversation-fabric` — the one canonical development branch.

## Validation rule

Every consolidation/cleanup change on `develop/conversation-fabric` must pass the normal exact-head verification gates before that head becomes a trusted development baseline. Branch cleanup itself must not mutate `main`, `chat-bridge-state` or `operator-control`.
