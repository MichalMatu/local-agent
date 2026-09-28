# Host Ops multirepo planner scope

`host-ops` is the canonical Chat Bridge operator workspace for cross-repository work.

## Binding model

A ChatGPT conversation still stores one immutable Bridge binding. The binding catalog additionally assigns a planner scope:

- `repository` — the normal default; the planner may work only on the bound repository and must explicitly rebind before acting elsewhere;
- `multirepo` — the planner may work across repositories present in the current validated runtime catalog without changing the conversation binding.

The canonical `host-ops` binding is the first `multirepo` binding. This is an explicit catalog property, not a repository-name heuristic.

```text
host-ops conversation binding
        |
        +--> MichalMatu/host-ops
        +--> MichalMatu/growclip
        +--> MichalMatu/MatrixHub
        +--> MichalMatu/tracker
        +--> MichalMatu/shelly-link
        +--> other current catalog repositories
```

Normal repository bindings remain fail-closed and single-repository.

## Target repository identity

The conversation binding authorizes the planner scope. It does not replace target-repository identity.

For every target repository the planner must resolve the exact current runtime-catalog record and use that repository's own canonical identity. It must never derive a repository id or binding UUID from prose, filesystem names, previous conversations or model memory.

For a Local Agent task targeting repository `X`:

```text
task.agent_binding == canonical agent_binding for repository X
```

The task does **not** inherit the `host-ops` binding merely because the conversation is bound to `host-ops`.

Executor validation remains unchanged: registry binding, repository control binding and task binding must match before commands execute. Repository leases, resource admission, watchdogs, cancellation ownership and durable evidence remain repository-scoped.

## Execution-disabled targets

A multirepo planner may inspect or edit a catalog repository through direct GitHub operations even when that catalog entry is `execution_enabled: false`.

It may not create a Local Agent project task for an execution-disabled target. In particular, the canonical `local-agent` entry remains intentionally non-executable by Local Agent itself. Source changes and CI work on `MichalMatu/local-agent` are therefore valid from a `host-ops` multirepo conversation without rebinding, while Local Agent self-execution remains separately protected.

Changing that self-execution policy would be a distinct executor/security decision and is not implied by multirepo planner scope.

## Chat Bridge behavior

Every wake still carries the immutable conversation envelope:

```text
[LA_AGENT=<conversation binding>]
[LA_REPO=<conversation repository id>]
[LA_REPOSITORY=<conversation repository>]
[LA_CHAT=<conversation id>]
```

For `planner_scope=multirepo`, the wake additionally includes the validated runtime catalog with repository ids, repository names, canonical bindings and execution state. The planner may move between those catalog targets as the active goal requires without `LAB:REBIND`.

`LAB:REBIND` remains the explicit mechanism for changing the conversation's own binding. It is not part of normal cross-repository work inside a multirepo operator conversation.

## External Bridge recovery

Bridge-native diagnostics and maintenance remain the primary recovery path while the extension can answer its own protocol. If the Bridge/content path itself is unavailable, the `host-ops` multirepo workspace may use the explicit external fallback documented in [External Chat Bridge recovery through Host Ops](BRIDGE_HOSTOPS_RECOVERY.md).

That fallback keeps the repository boundary intact: `local-agent` remains execution-disabled, while a machine action is queued only against the execution-enabled `host-ops` repository using the exact `host-ops` binding. The helper requires an explicit loopback CDP endpoint and exact conversation URL, defaults to read-only readiness, and allows at most one Host Ops guarded page reload when `--recover` is explicitly requested and readiness classifies the content script as missing or stale.

It is not a worker restart mechanism and must not become an automatic daemon watchdog or reload loop.

## Security properties

Multirepo scope deliberately changes planner authorization, not executor trust boundaries:

- only catalog-declared `multirepo` bindings receive cross-repository planner authority;
- unknown planner scopes fail closed during runtime parsing;
- `multirepo` is rejected for an execution-disabled binding;
- target identities come only from the current runtime catalog;
- target Local Agent tasks retain the target repository's canonical binding;
- normal repository-scoped conversations preserve the existing single-repository policy;
- global emergency controls, repository leases and task/resource limits are unchanged.

This separation allows a `host-ops` chat to behave as one practical operator workspace without turning `host-ops` into a scheduler or weakening Local Agent's repository isolation.

## Downstream documentation audit

The registered project repositories keep `planner_scope=repository`, so their existing project-chat contract remains unchanged: a directly project-bound conversation is still single-repository and every Local Agent task still carries that project's exact binding.

The release audit therefore does not require project-document rewrites merely to introduce the `host-ops` operator scope or its external Bridge recovery fallback. The reviewed downstream instructions continue to describe target-repository task binding and repository-scoped execution correctly. If a downstream repository later gains its own `multirepo` scope or begins documenting the `host-ops` operator workspace, that repository's planner documentation must be updated explicitly.
