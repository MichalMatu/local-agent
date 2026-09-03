# Emergency Local Agent controls

Local Agent 4.14.1 adds bounded emergency controls intended for autonomous chat-driven operation.

## Remote control request

A chat may publish `.agent/daemon/control.json` on the `agent-control` branch of the repository that owns the conversation.

Cancel one task:

```json
{
  "id": "cancel-<unique-id>",
  "action": "cancel_task",
  "task_id": "<exact-task-id>"
}
```

Disable Local Agent globally:

```json
{
  "id": "disable-<unique-id>",
  "action": "disable"
}
```

`disable` creates the persistent local marker:

`~/Library/Application Support/local-agent/disabled.json`

The parallel supervisor stops active workers and admits no new tasks while this marker exists. The marker survives supervisor and launchd restarts.

## Local recovery

The emergency disable is intentionally not remotely reversible. Re-enable explicitly on the Mac:

```bash
cd ~/local-agent
.venv/bin/python agent_operator.py enable
```

Inspect state:

```bash
.venv/bin/python agent_operator.py status
```

Disable locally:

```bash
.venv/bin/python agent_operator.py disable --reason operator_cli
```

## Safety rules

- `cancel_task` requires the exact immutable task id.
- A cancel request for another active task is rejected.
- Pending cancellation publishes a terminal `cancelled_by_operator` result before later admission.
- Active cancellation is accepted only by the worker that owns the target repository/task.
- `disable` is global and fail-closed: a malformed but present disable marker still blocks admission.
- Re-enable is local and explicit so a chat cannot accidentally undo an emergency stop.
