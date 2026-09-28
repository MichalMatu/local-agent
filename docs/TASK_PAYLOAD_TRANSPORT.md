# Task payload transport

Local Agent supports an escape-safe task transport for source text that is awkward or fragile to embed directly in JSON. Legacy inline `.agent/tasks/<queue-name>.json` tasks remain valid and unchanged.

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

## Producer path

`local_agent.runtime.task_transport.write_task_bundle()` is the canonical local producer helper. It validates the canonical task first, writes payload files, serializes the manifest with Python's JSON encoder, and exposes the manifest last. A producer error therefore cannot enqueue a visible manifest before its payloads exist.

`externalize_task_payloads()` provides the same deterministic transformation without filesystem writes for integrations that publish the resulting files through another transport such as Git.

The runtime materializes payload references before normal contract validation and before the immutable task digest is calculated. The resolved task therefore has the same digest as the equivalent legacy inline task.

## Failure and replay policy

Malformed JSON remains terminal `invalid_task_file`. Local Agent does not guess how broken JSON should have been escaped and does not automatically replay or repair a rejected task. The payload transport prevents escape-heavy source text from entering JSON in the first place; it does not weaken the existing no-replay invariant.

Missing or invalid payload files are also terminal task validation failures before claim or command execution. Runtime cleanup removes retained payload files together with an expired terminal task/result pair.
