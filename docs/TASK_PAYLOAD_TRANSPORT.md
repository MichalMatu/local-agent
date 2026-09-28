# Task payload transport

Local Agent 4.19.2 adds an escape-safe task transport for source text that is awkward or fragile to embed directly in JSON. Legacy inline `.agent/tasks/<queue-name>.json` tasks remain valid and unchanged.

## Runtime compatibility

Use `payload_file` only after the target repository reports Local Agent 4.19.2 or newer and the expected released `self_revision`. Older runtimes do not understand this representation; keep using legacy inline strings until that runtime has been upgraded.

## Planner rule

Use the external payload form for source-like or multiline text that would otherwise require manual JSON escaping, especially generated code, HTML/CSS/JS, shell/Python snippets, large write bodies and unified diffs. Do not hand-build a giant escaped JSON string when the same bytes can be committed as a normal UTF-8 payload file.

The task manifest remains the queue identity and must still be published as `.agent/tasks/<queue-name>.json`. Publish the manifest and every referenced payload file in the same `agent-control` Git commit so the executor never observes a manifest without its referenced text. Inline strings remain supported for small/simple values and do not require migration.

## Layout

A task manifest stays in the existing queue location and text payloads live beside it under a task-id-scoped directory:

```text
.agent/tasks/layout-42.json
.agent/tasks/layout-42.payload/patch.diff
.agent/tasks/layout-42.payload/writes/001.txt
.agent/tasks/layout-42.payload/commands/001.sh
.agent/tasks/layout-42.payload/verify-commands/001.sh
```

The JSON envelope contains only normal task metadata plus file references:

```json
{
  "id": "layout-42",
  "resources": [],
  "commands": [
    {"payload_file": "layout-42.payload/commands/001.sh"}
  ],
  "writes": [
    {
      "path": "src/layout.js",
      "content": {"payload_file": "layout-42.payload/writes/001.txt"}
    }
  ]
}
```

`payload_file` is accepted only for text-bearing task fields:

- `patch`
- `writes[].content`
- `commands[]`
- `verify_commands[]`
- `steps[].command`
- `verify_steps[].command`

Each reference must be canonical relative POSIX text under `<task-id>.payload/`. Symlinks, path traversal, missing files, invalid UTF-8 and existing task field limits fail closed during task validation.

The resolved logical task remains bounded by the existing `MAX_TASK_FILE_BYTES` limit. External files remove JSON escaping fragility; they do not increase the maximum logical task size. Reusing one payload file from many fields cannot amplify a small on-disk payload into an oversized effective task.

## Producer path

`local_agent.runtime.task_transport.write_task_bundle()` is the canonical local producer helper. It validates the canonical task first, exclusively reserves the task payload directory, writes payload files, serializes the manifest with Python's JSON encoder, and exposes the manifest last. An existing manifest or payload reservation fails closed rather than being overwritten.

`externalize_task_payloads()` provides the same deterministic transformation without filesystem writes for integrations that publish the resulting files through another transport such as Git.

The runtime materializes payload references before normal contract validation and before the immutable task digest is calculated. The resolved task therefore has the same digest as the equivalent legacy inline task.

## Failure and replay policy

Malformed JSON remains terminal `invalid_task_file`. Local Agent does not guess how broken JSON should have been escaped and does not automatically replay or repair a rejected task. The payload transport prevents escape-heavy source text from entering JSON in the first place; it does not weaken the existing no-replay invariant.

Missing or invalid payload files are also terminal task validation failures before claim or command execution. Runtime cleanup removes retained payload files together with an expired terminal task/result pair without following payload symlinks or trusting malformed embedded task ids.

## Downstream compatibility audit

The registered project instructions were re-audited before merge. GrowClip and MatrixHub explicitly describe `.agent/tasks/<task-id>.json`, while BloomML and Tracker keep only repository-specific task/binding rules. Those instructions remain correct because the JSON manifest is still mandatory and legacy inline text remains valid. The previously documented BloomML `mvp/environment-controller` branch no longer exists, so there is no active second branch copy to synchronize. No downstream migration is required; the new payload directory is an additive escape-safe representation owned by the canonical Local Agent runtime documentation.
