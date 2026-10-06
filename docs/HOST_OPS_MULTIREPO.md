# Superchat multirepo reasoning and absorbed Host Ops

A parent Superchat may coordinate reasoning across multiple repositories without rebinding the Chat Bridge conversation. Repository reasoning scope comes from the active goal and durable request. It does not require a dedicated multirepo execution repository.

## Execution boundary

Every executable task still targets exactly one canonical execution-enabled repository and carries that repository's exact `agent_binding`. Chat identity, donor repositories and reasoning scope never substitute for execution authority.

Mac-local/host-maintenance work targets `local-agent` and uses the absorbed `local_agent.host_ops` subsystem. The standalone `MichalMatu/host-ops` repository is retired from the canonical execution catalog and is retained only as frozen donor/history evidence.

The executor continues to enforce repository binding equality, repository leases, resource admission, watchdogs, cancellation ownership and durable run/result evidence.

## Cross-repository reasoning

Conversation Fabric children remain reasoning-only. They may inspect and compare bounded donor/target evidence from multiple repositories when the parent goal requires it, but they do not create executable tasks or inherit authority from any donor repository.

For executable work:

1. resolve the actual target from the canonical catalog;
2. require `execution_enabled=true`;
3. use the exact target binding in the task;
4. use direct GitHub edits when repository-side diff + CI is sufficient;
5. use `local-agent` host-maintenance tasks only when machine-local commands, builds, devices or host state are genuinely required.

There is no `host-ops` planner scope, execution binding or compatibility workspace in the current source/runtime catalog.
