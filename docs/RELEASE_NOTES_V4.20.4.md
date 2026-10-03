# Local Agent 4.20.4

## Summary

Local Agent 4.20.4 removes repository binding from the Superchat conversation/transport layer while preserving exact repository binding at the only consequential boundary: executable `.agent/tasks`.

Chat Bridge advances to 0.8.0. A managed ChatGPT conversation is now a transport and scheduling channel, not a repository execution identity. Repository scope may be supplied by the active goal or durable Conversation Fabric operator request and may include multiple repositories, including donor and target repositories, without rebinding the chat.

## Changes

- Add operator request schema v3 with ordered `repository_ids` reasoning context for multirepo and donor/target work.
- Preserve schema v1/v2 compatibility while stopping v2 `repository_id` from injecting target execution identity into a child campaign.
- Remove the Conversation Fabric `operator_target` execution-identity resolver from the reasoning boundary.
- Keep child conversations reasoning-only and state explicitly that repository fields in child bootstrap records are provenance/reasoning context, not machine execution authority.
- Make Chat Bridge onboarding transport-only: a concrete chat can be managed without selecting a repository binding first.
- Use the multirepo transport workspace as compatibility metadata when a new chat has no legacy binding metadata.
- Make GitHub `conversation_controls` ownership chat-scoped instead of coupling schedule authority to repository/binding revision.
- Keep legacy Bridge rebind handling only as compatibility metadata/epoch refresh so stale-generation and race guards remain intact.
- Remove hard-repository scope language from Bridge bootstrap/wake prompts; every executable Local Agent task must still resolve the actual target and carry that target repository's exact canonical `agent_binding`.
- Update isolated Chromium/browser smoke coverage for the transport-only chat envelope and popup guidance.

## Safety boundary retained

This release does **not** weaken Local Agent execution admission. `.agent/tasks` remains the only executable repository-work contract. Repository registry/catalog validation, `execution_enabled`, origin identity, repository lease, task digest, and exact canonical target `agent_binding` checks remain enforced at execution time.

Production/daily Chrome is not part of the release validation path; browser validation uses isolated test/lab profiles.
