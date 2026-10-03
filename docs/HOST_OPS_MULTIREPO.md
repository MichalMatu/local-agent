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

For every Local Agent task, resolve the actual target repository and use that repository's exact canonical binding:

```text
registry binding == .agent/binding.json binding == task.agent_binding
```

The task never inherits the `host-ops` binding merely because the parent Superchat uses Host Ops for orchestration. Executor validation, repository leases, resource admission, watchdogs, cancellation ownership and durable evidence remain repository-scoped.

## Donor repositories

A donor repository can be inspected, compared or edited through permitted GitHub operations while another repository is the executable target. Donor context never grants machine authority over the target.

The canonical `local-agent` catalog entry is intentionally `execution_enabled: false`; Local Agent source can be inspected or edited through GitHub, but Local Agent must not queue an executable `.agent/tasks` item against its own disabled catalog entry.

## Chat Bridge behavior

A normal wake uses only the stable chat envelope plus the runtime prompt:

```text
[LA_CHAT=<conversation id>]
```

GitHub `conversation_controls` owns pacing for managed chats. Repository/binding fields are not schedule authority. Legacy ADD/REBIND controls remain migration compatibility only.

## Host Ops

Use the execution-enabled `host-ops` repository only for bounded Mac-local operations that genuinely belong to Host Ops: inspecting worktrees/process state, running local release gates, managing isolated development profiles or other host-level operations. Project work belongs to the actual project repository and uses that project's exact task binding.

## Child reasoning

Child chats, when used, are reasoning-only. They may audit, debug, compare donor/target code and propose fixes. They never receive independent machine execution authority; the parent Superchat decides what becomes executable work and queues only exact-bound target tasks.

The current browser child-spawn path has a known `chatgpt_login_timeout` detector failure in the isolated profile. Do not repeat login/Cloudflare/DOM loops as a parent-Superchat acceptance gate. Treat child-browser transport as a separately repairable component while the parent continues operating.

## Security properties

- chat identity is transport/scheduling identity only;
- repository reasoning context does not grant execution authority;
- every executable task uses the target repository's exact canonical binding;
- execution-disabled targets never receive executable tasks;
- global emergency controls, repository leases and task/resource limits remain unchanged;
- GitHub remains the durable control/evidence plane.
