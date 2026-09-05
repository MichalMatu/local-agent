# Emergency Local Agent controls

Local Agent 4.14.2 adds repository-independent emergency stop and bounded task cancellation for autonomous chat-driven operation.

## Central emergency stop

The global kill switch no longer depends on any project repository checkout. The always-on guarded entrypoint polls the `operator-control` branch of `MichalMatu/local-agent` and reads:

`.agent/operator/state.json`

Normal state:

```json
{
  "version": 1,
  "desired_state": "enabled",
  "request_id": "operator-control-bootstrap"
}
```

Emergency stop from chat changes only the desired state and request id:

```json
{
  "version": 1,
  "desired_state": "disabled",
  "request_id": "disable-<unique-id>"
}
```

The guarded entrypoint persists:

`~/Library/Application Support/local-agent/disabled.json`

and terminates the parallel supervisor process group. While the marker exists it does not start a new supervisor, even when launchd has `KeepAlive=true`.

Remote `desired_state=enabled` never clears the local marker. Re-enable remains an explicit local action.

## Repository task cancellation

A chat may publish `.agent/daemon/control.json` on the `agent-control` branch of the repository that owns the conversation.

Cancel one task:

```json
{
  "id": "cancel-<unique-id>",
  "action": "cancel_task",
  "task_id": "<exact-task-id>"
}
```

Pending cancellation publishes a terminal `cancelled_by_operator` result. Active cancellation is accepted only by the worker that owns the exact repository/task.

## Local recovery

Before re-enabling after a destructive remote queue reset, clear local ephemeral claims/result spool while the agent is disabled:

```bash
cd ~/local-agent
.venv/bin/python -m local_agent.operator.local reset-runtime
```

The command refuses to run unless the persistent disable marker exists. It clears only local ephemeral runtime (`claims`, `corrupt-claims`, `runs`, `result-spool`, repository status), not repositories, checkpoints, registry configuration, or the disable marker.

Re-enable explicitly on the Mac only after the remote operator desired state is `enabled`:

```bash
.venv/bin/python -m local_agent.operator.local enable
```

Inspect state:

```bash
.venv/bin/python -m local_agent.operator.local status
```

Disable locally:

```bash
.venv/bin/python -m local_agent.operator.local disable --reason operator_cli
```

## Startup repair

Before starting the parallel supervisor, the guarded entrypoint performs only bounded repairs:

- removes generated Python bytecode under `.agent/patches/**/__pycache__` and `*.pyc`/`*.pyo`;
- provisions a repository checkout only when its control or work checkout is completely missing;
- sets `PYTHONDONTWRITEBYTECODE=1` for the supervisor and workers.

Existing but mismatched/dirty repositories are not destructively replaced.

## Safety rules

- Global emergency stop uses the central Local Agent control branch and therefore does not depend on Growbox/C6/LiteGraph/MatrixHub health.
- `cancel_task` requires the exact immutable task id.
- A cancel request for another active task is rejected.
- `disable` is persistent and fail-closed locally: a malformed but present disable marker still blocks admission.
- Remote state cannot re-enable the local agent.
- Local runtime reset is destructive only for ephemeral state and requires disabled mode.
- Missing workspaces may self-provision, but an existing unexpected checkout is never overwritten automatically.
