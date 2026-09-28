# Local Agent 4.19.1

## Summary

Release an explicit multirepository planner scope for the canonical `host-ops` Chat Bridge binding while preserving Local Agent's exact target-repository execution identity and all existing executor isolation. The same candidate also adds an additive escape-safe task payload transport so source-like text no longer has to be hand-escaped into one large task JSON document.

The conversation itself remains immutably bound to `host-ops`. That binding now authorizes ChatGPT to move between repositories present in the current validated runtime catalog without an operator Rebind. Normal repository bindings remain single-repository and fail closed exactly as before.

## Planner scope

The canonical binding catalog and Chat Bridge runtime now carry `planner_scope`:

- `repository` is the default and retains the existing one-conversation/one-target policy;
- `multirepo` is explicit catalog authorization for an operator workspace;
- the canonical `host-ops` entry is the initial `multirepo` binding.

A multirepo planner may target only repositories present in the validated runtime catalog. Repository ids, remote names and binding UUIDs must come from that catalog and must never be inferred from prose, paths, previous conversations or model memory.

## Executor isolation remains exact

Planner authorization does not replace repository execution identity. A Local Agent task for target repository `X` still requires:

```text
registry X agent_binding
    == X/.agent/binding.json agent_binding
    == task.agent_binding
```

The `host-ops` conversation binding is never copied into a task for another repository. Repository leases, resource admission, task digests, watchdogs, cancellation ownership, run/result evidence and emergency controls remain target-repository scoped.

The `local-agent` catalog entry remains intentionally `execution_enabled: false`. A `host-ops` multirepo conversation may inspect or edit `MichalMatu/local-agent` through direct GitHub operations, but it may not bypass Local Agent's self-execution protection by queueing a Local Agent task for that target.

## Chat Bridge 0.5.11

Chat Bridge advances from 0.5.10 to 0.5.11 because the service-worker routing policy changes materially:

- validated runtime agents carry planner scope;
- repository scope keeps the existing hard target restriction;
- multirepo scope includes validated target identities in the wake policy and allows target changes without changing the conversation binding;
- unknown scope values fail closed;
- multirepo authorization is not accepted on an execution-disabled operator binding.

Ordinary ChatGPT DOM submission behavior is unchanged, so content protocol remains v7. Assistant timeout/exhaustion guard protocol remains v3.

## Escape-safe task payload transport

Task manifests remain `.agent/tasks/<queue-name>.json`, but text-bearing fields may now reference ordinary UTF-8 files under `.agent/tasks/<task-id>.payload/` through a strict `payload_file` object. Supported fields are `patch`, `writes[].content`, `commands[]`, `verify_commands[]`, `steps[].command` and `verify_steps[].command`.

The runtime materializes those references before normal validation and digest calculation. The resulting digest is therefore identical to the equivalent legacy inline task. References are restricted to the task-id-scoped payload directory; path traversal, symlinks, missing files and invalid UTF-8 fail closed before claim or command execution.

The transport removes JSON escaping fragility but does not relax existing task bounds. The fully resolved logical task remains capped by the existing 4 MiB task-file limit, including repeated-reference amplification. Runtime GC removes retained payload files together with expired terminal task/result pairs.

Malformed task JSON remains terminal `invalid_task_file`. The daemon does not guess how broken JSON should have been escaped, rewrite it or replay it automatically.

## Compatibility

This release adds an optional, backward-compatible task representation; it does not remove or reinterpret legacy inline strings. Existing task JSON remains valid without migration, and task ids, digests after materialization, hard-binding admission, scheduler/resource semantics, repository worker behavior, process lifecycle, self-update mechanism, MCP transport and emergency-control authority remain unchanged.

Registered downstream planner instructions were re-audited. GrowClip and MatrixHub explicitly describe the JSON task manifest path, while BloomML and Tracker keep repository-specific binding/task rules. Those instructions remain accurate because the manifest remains mandatory and inline payloads remain supported, so no downstream source-document migration is required. Canonical payload guidance lives in `TASK_PAYLOAD_TRANSPORT.md`.

## Verification gate

Before advancing `main`, the exact final candidate SHA must pass:

- compile and Ruff;
- full Python unit/integration suite and coverage;
- Python 3.14 compatibility;
- task-payload regressions covering escape-heavy round-trip, path containment, missing payloads, legacy inline compatibility, resolved-size amplification and runtime cleanup;
- Chat Bridge static/unit tests including multirepo positive/negative routing coverage;
- isolated real-extension Bridge browser smoke;
- macOS smoke;
- current-documentation/release-metadata drift checks;
- final architecture/diff review confirming executor admission was not widened.

Production baseline before this release is `v4.19.0` at `1ea863d06a20e766f9fe0fa5589cc59aa0e2671a`. The published Local Agent status for the canonical `host-ops` repository has confirmed daemon version `4.19.0`, that exact self revision, parallel multi-repository-worker execution and idle state. The 4.19.1 candidate remains unreleased until the explicit release decision advances `main` and the matching release tag is created.

## Deployment

After release:

1. advance the installed `~/local-agent` checkout through the normal validated self-update/restart path;
2. reload the unpacked Chat Bridge so the popup/diagnostics report 0.5.11;
3. keep the existing conversation binding to `host-ops`; no replacement binding is required;
4. verify a normal repository-scoped chat still rejects cross-repository planner work;
5. verify a `host-ops` conversation receives `planner_scope=multirepo` and can resolve another catalog repository without Rebind;
6. for any Local Agent task created from that conversation, verify the task uses the target repository's exact canonical binding rather than the `host-ops` conversation binding;
7. for escape-heavy task content, publish the JSON manifest and referenced `.payload/` files together in one `agent-control` commit and verify the resolved task digest/result evidence.
