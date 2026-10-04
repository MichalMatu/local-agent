# Superchat multirepo reasoning and Host Ops transport workspace

A parent Superchat may coordinate work across multiple repositories without rebinding the Chat Bridge conversation. `host-ops` remains the canonical execution-enabled operator/transport workspace for Mac-local operations, but its Bridge metadata does not grant repository execution authority.

## Repository scope

Repository scope comes from the active user goal or a durable Conversation Fabric request. It may include donor and target repositories, for example:

```text
parent Superchat
  reasoning context: local-agent + growclip
  donor: local-agent
  execution target: growclip
```

`repository_id` / `repository_ids` are reasoning context only. Legacy `planner_scope`, `repositoryId`, `agentBinding` and binding-revision values may remain in Bridge/runtime state for compatibility or transport-workspace selection; they are not security boundaries and normal work must not use `LAB:REBIND` to switch targets.

## Executable target identity

For every Local Agent task, resolve the actual target through the canonical runtime catalog before queueing work. The catalog record must exist, `execution_enabled` must be true, and the exact canonical target binding must agree end-to-end:

```text
canonical catalog binding == registry binding == .agent/binding.json binding == task.agent_binding
```

Registry/control agreement without the canonical catalog record is not sufficient execution authority and fails closed.

The task never inherits the `host-ops` binding merely because the parent Superchat uses Host Ops for orchestration. Executor validation, repository leases, resource admission, watchdogs, cancellation ownership and durable evidence remain repository-scoped.

## Donor repositories

A donor repository can be inspected, compared or edited through permitted GitHub operations while another repository is the executable target. Donor context never grants machine authority over the target.

The current canonical `local-agent` catalog entry is execution-enabled. Local Agent may queue executable work against its own repository only with the exact canonical `local-agent` binding; self-execution does not relax catalog admission, registry/control/task binding equality, leases, resource admission or emergency controls.

## Chat Bridge behavior

A normal wake uses only the stable chat envelope plus the runtime prompt:

```text
[LA_CHAT=<conversation id>]
```

GitHub `conversation_controls` owns pacing for managed chats. Repository/binding fields are not schedule authority. Legacy ADD/REBIND controls remain migration compatibility only.

## Host Ops

Use the execution-enabled `host-ops` repository only for bounded Mac-local operations that genuinely belong to Host Ops: inspecting worktrees/process state, running local release gates, managing host services or other machine-level operations. Project work belongs to the actual project repository and uses that project's exact task binding.

Use direct GitHub edits when an exact source/docs diff plus CI is sufficient. Use Local Agent only when the task genuinely requires machine-local commands, local builds/tests, devices or host state.

## Child reasoning

Conversation Fabric children are reasoning-only. They may audit, debug, compare donor/target code and propose fixes, but they do not create `.agent/tasks`, run machine commands, mutate repositories or make the final execution decision.

Production child delegation uses ordinary tabs in the operator's already authenticated primary Chrome session. The retired isolated-profile/login path is historical development tooling only and is not a production acceptance or recovery mechanism.

Campaign/result recovery is durable in Bridge local storage. Child ownership after worker/session restart must be proven by exact transaction/request/bootstrap/current-URL evidence, not a reused tab id. Explicit collect may inspect/recover already-submitted children but must never replay their prompts.

## Security properties

- chat identity is transport/scheduling identity only;
- repository reasoning context does not grant execution authority;
- the canonical runtime catalog is mandatory final admission authority;
- every executable task uses the target repository's exact canonical binding;
- execution-disabled targets never receive executable tasks;
- self-execution for `local-agent` uses the same hard binding and repository isolation rules as every other execution-enabled target;
- global emergency controls, repository leases and task/resource limits remain unchanged;
- GitHub remains the durable control/evidence plane;
- Conversation Fabric children remain reasoning-only and cannot upgrade browser transport into machine execution authority.
