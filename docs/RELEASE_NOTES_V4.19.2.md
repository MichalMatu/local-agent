# Local Agent 4.19.2

## Summary

Release an additive escape-safe task payload transport so source-like multiline text no longer has to be hand-escaped into one large task JSON document.

The queue identity remains `.agent/tasks/<queue-name>.json`. Text-bearing task fields may instead reference ordinary UTF-8 files stored under `.agent/tasks/<task-id>.payload/`. Legacy inline task strings remain valid and require no migration.

## Task payload transport

`payload_file` references are supported only for:

- `patch`;
- `writes[].content`;
- `commands[]`;
- `verify_commands[]`;
- `steps[].command`;
- `verify_steps[].command`.

References must be canonical relative POSIX paths rooted under the exact `<task-id>.payload/` directory. Missing payloads, path traversal, symlinks and invalid UTF-8 fail closed before claim or command execution.

The runtime materializes referenced text before normal task validation and before calculating the immutable task digest. The resolved task therefore has the same digest as the equivalent legacy inline task.

External payload files remove JSON escaping fragility; they do not relax execution bounds. The fully resolved logical task remains capped by the existing 4 MiB task-file limit, including repeated-reference amplification, and existing patch/write/command limits remain in force.

## Publication and cleanup safety

`local_agent.runtime.task_transport.write_task_bundle()` validates the canonical task first, reserves the task payload directory exclusively, writes payload files, and exposes the JSON manifest last. It refuses an existing manifest or payload reservation rather than overwriting another producer's task state.

For Git-backed producer paths, the JSON manifest and all referenced payload files must be published in the same `agent-control` commit.

Runtime GC removes retained payload files together with expired terminal task/result pairs. Cleanup does not follow payload symlinks, rejects non-canonical deletion paths, and ignores malformed embedded task ids rather than deriving cleanup targets from them.

Malformed task JSON remains terminal `invalid_task_file`. Local Agent does not guess how broken JSON should have been escaped and does not automatically repair or replay a rejected task.

## Compatibility

This is an additive task representation change. Existing inline task JSON remains valid and keeps identical scheduler, resource, binding, watchdog, repository-worker, result and emergency-control semantics.

The new `payload_file` representation requires a Local Agent runtime at 4.19.2 or newer. Planners must continue using legacy inline strings while the target repository reports an older daemon/runtime revision.

Chat Bridge behavior does not change in this release; Bridge remains 0.5.11 with content protocol v7 and assistant timeout/exhaustion guard protocol v3.

Registered downstream planner instructions were re-audited. Their existing `.agent/tasks/<task-id>.json`, binding and resource rules remain correct because the manifest is still mandatory and inline payloads remain supported. The previously documented BloomML `mvp/environment-controller` branch no longer exists, so there is no second branch copy to synchronize there.

## Verification gate

Before advancing `main`, the exact final candidate SHA must pass:

- compile and Ruff;
- full Python unit/integration suite and coverage;
- Python 3.14 compatibility;
- escape-heavy payload round-trip and digest equivalence;
- resolved-size amplification rejection;
- payload path, symlink, missing-file and UTF-8 guards;
- collision-safe bundle publication regressions;
- runtime cleanup path/task-id safety regressions;
- isolated real-extension Bridge browser smoke;
- macOS smoke;
- current-documentation/release-metadata drift checks;
- final `main...candidate` diff review.

The previous released baseline is tagged `v4.19.1` at commit `4cb19ec998acdf48462021c2821f488095e69442`. The 4.19.2 candidate remains unreleased until the explicit release decision advances `main` and creates the matching tag.

## Deployment

After release:

1. advance the installed `~/local-agent` checkout through the normal validated self-update/restart path;
2. confirm `daemon_version` reports 4.19.2 and `self_revision` is the released 4.19.2 commit before publishing any task that uses `payload_file`;
3. no Chat Bridge reload is required solely for this runtime change;
4. keep using legacy inline task strings for any repository still served by an older runtime;
5. for an externalized task, publish the manifest and every referenced `.payload/` file in one control-branch commit and verify the terminal result/digest evidence normally.
