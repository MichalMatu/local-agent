# Multirepo reasoning after Host Ops absorption

A parent Superchat may coordinate reasoning across multiple repositories without rebinding the Chat Bridge conversation. Chat identity is transport/scheduling identity only; repository scope comes from the active user goal or a durable Conversation Fabric request.

The former standalone `MichalMatu/host-ops` repository is **not** a canonical execution target. Its maintained production capabilities live under `local_agent.host_ops` and host-maintenance work targets `local-agent` with the normal Local Agent binding.

## Repository scope

Reasoning may include donor and target repositories, for example:

```text
parent Superchat
  reasoning context: local-agent + growclip
  donor/reference: local-agent
  execution target: growclip
```

Repository names in the goal or child request are reasoning context only. Legacy `planner_scope`, `repositoryId`, `agentBinding` and binding-revision fields may still be parsed from historical Bridge state, but they are not execution authority and no current runtime agent is privileged as a special `multirepo` workspace.

## Executable target identity

For every executable task, resolve the actual target through the canonical runtime catalog. The catalog record must exist, `execution_enabled` must be true, and the same canonical binding must agree end-to-end:

```text
canonical catalog binding == registry binding == .agent/binding.json binding == task.agent_binding
```

Registry/control agreement without the canonical catalog record is insufficient and fails closed. Donor context, chat identity and absorbed host tooling never substitute for target authorization.

The canonical `local-agent` record is execution-enabled. Host-maintenance tasks use that target and the internal `local_agent.host_ops` capability layer. Self-execution does not relax catalog admission, registry/control/task binding equality, repository leases, resource admission, watchdogs or emergency controls.

## Chat Bridge behavior

Normal bootstrap/wake messages use the stable chat envelope:

```text
[LA_CHAT=<conversation id>]
```

GitHub `conversation_controls` owns pacing for managed chats. Repository/binding metadata is not schedule authority. Legacy ADD/REBIND and planner-scope behavior are compatibility parsing only and must not be used to create a second execution identity.

Use direct GitHub edits when an exact source/docs diff plus CI is sufficient. Use Local Agent only when work genuinely requires machine-local commands, local builds/tests, devices or host state.

## Child reasoning

Conversation Fabric children are reasoning-only. They may audit, compare donor/target code and propose fixes, but they do not create `.agent/tasks`, execute machine commands, mutate repositories or make the final execution decision.

Production child delegation uses ordinary tabs in the operator's authenticated primary Chrome session. Campaign/result recovery remains durable in Bridge local storage, and ambiguous ownership fails closed.

## Security properties

- chat identity is transport/scheduling identity only;
- repository reasoning context does not grant execution authority;
- the canonical runtime catalog is mandatory final admission authority;
- every executable task uses the target repository's exact canonical binding;
- execution-disabled or absent targets never receive executable tasks;
- host/remote capability code lives under `local_agent.host_ops`, not a separate Host Ops executor;
- global emergency controls, repository leases and task/resource limits remain unchanged;
- GitHub remains the durable control/evidence plane;
- Conversation Fabric children remain reasoning-only.
