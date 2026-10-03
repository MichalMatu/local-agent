# Local Agent 4.20.1

## Summary

Local Agent 4.20.1 is a bounded Conversation Fabric follow-up to 4.20.0. It lets an Operator Chat/Superchat request name one registered project repository for child reasoning while preserving the existing child lifecycle, GitHub durability and `.agent/tasks` execution boundary. Chat Bridge remains 0.7.0.

## Target-repository operator requests

- Operator request schema v2 adds one required request-level `repository_id`; schema v1 remains accepted for the original Local Agent DEV identity.
- Local Agent resolves the target through the runtime repository registry and canonical binding catalog instead of trusting model-supplied repository metadata.
- The target must be execution-enabled, have an exact canonical binding match, use a matching GitHub origin and resolve its configured default branch to one canonical remote commit SHA.
- The immutable repository id/name, binding, ref and commit SHA are injected into the existing Conversation Fabric child request/bootstrap identity.
- The accepted `run_mvp_campaign()` lifecycle remains the semantic owner; no second lifecycle or scheduler is introduced.

## Execution authority

- Child chats remain reasoning-only and receive no independent host or repository execution authority.
- `.agent/tasks` remains the only executable repository-work contract. Any resulting edits, builds or tests must use the exact canonical binding of the target repository through the existing Local Agent worker path.
- This release does not change task schema, resource semantics, executor admission, scheduler concurrency or self-update behavior.

## Chat Bridge and rollout

- Chat Bridge stays at 0.7.0; runtime schema 3, content protocol v13 and assistant guard v8 are unchanged.
- No production Chrome/profile mutation is required by this source change.
- Conversation Fabric operator intake remains default-disabled and unconfigured until an explicit production activation decision.
- One intended parent conversation must be explicitly onboarded as the managed Superchat/wake target before an autonomous pilot; existing disabled managed chats are not implicitly reused.
- The prior DEV login/Cloudflare live-proof loop is not a release requirement for this change and must not be repeated automatically.

## Development evidence

- Focused target/contract/campaign/supervisor suite: 30 tests passed on development checkpoint `e05a5d808327252f33da7b3d0dd1821878273b95`.
- Read-only real-target resolution proved `growclip` and `shelly-link` resolve through the live runtime registry to their canonical bindings and current remote `main` SHAs without mutating either repository.
- Exact-SHA CI run `37096078760` passed all five jobs on that development checkpoint.

## Required final release gates

Before `main` may advance, the exact final 4.20.1 candidate including this release metadata must pass focused positive/negative tests, repository-wide verification, coverage, Python compatibility, macOS smoke and Bridge browser CI. Production `main`, operator intake and the production Chrome profile remain unchanged until a separate explicit release decision.
