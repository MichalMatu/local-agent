# Physical task progress and fail-fast evidence

Use this contract for Local Agent tasks that control real hardware or another long-running external process where the operator needs to know the exact current stage.

## Structured progress

Local Agent already recognizes stdout lines with this form:

```text
[AGENT_PROGRESS] {"stage_name":"device-live","stage_phase":"stream","message":"DRAWING 1200/4300","current":1200,"total":4300}
```

The JSON object is parsed by the runtime and published as stage progress, including `last_progress_at` and `last_progress_message` in remote run/status evidence. Use this mechanism instead of plain status text for meaningful physical checkpoints.

A long-running hardware command should emit a marker:

- after offline/preflight validation;
- after physical device identity is proven;
- after each safety-critical setup stage such as homing;
- when the primary physical operation begins;
- periodically during the operation, at least once per normal heartbeat window when practical;
- on bounded recovery/abort action;
- on successful final safe state.

## Evidence language

Do not infer a physical event from generic process liveness.

- `state=running`, a worker PID, recent heartbeat or `seconds_since_output` proves only that the process is alive/recently produced output.
- `HOMING_XY_OK` may be reported only after a corresponding structured progress marker or terminal output is available.
- `DRAWING_STARTED` may be reported only after its marker/evidence.
- Completion requires a terminal task result and, when applicable, an explicit final-safe-state marker such as `COMPLETE_PEN_UP`.

If only liveness is known, say only that the task is still running.

## Fail-fast operator communication

Do not hide recovery churn behind a long-running conversation.

1. When a required artifact, worker capability, executable, device identity or repository binding is missing/mismatched, surface the exact blocker immediately.
2. Diagnose the failed boundary before creating another task variant. Avoid speculative retry chains.
3. A tool available in one repository worker must not be assumed available in another worker environment.
4. Before starting or probing physical hardware, inspect the owning binding for an active task. Never create a competing device session while an existing physical task is running.
5. If a retry could duplicate or conflict with physical motion, require evidence that the previous attempt ended before retrying.
6. Do not convert a watchdog heartbeat into a claim about physical state.

## Multi-repository device workflows

Keep each responsibility on the worker that owns it:

- the device/project repository owns device-specific protocol, validation and safety policy;
- a generic capability repository such as `host-ops` owns generic host/device discovery and bounded transport primitives;
- Local Agent owns scheduling, watchdogs, repository identity and run/result evidence.

Cross-repository assistance is not a reason to bounce one physical transaction through multiple workers. Prefer one project-local live task after prerequisites are known, with generic probes used only when discovery or ambiguity actually requires them.

## Example: Kobra 2 Neo

The canonical implementation lives in `MichalMatu/hardware-lab/projects/kobra2-neo` and emits stages such as:

```text
PREFLIGHT_OK
PRINTER_IDENTIFIED
HOMING_XY_OK
HOMING_Z_OK
PEN_UP_OK
DRAWING_STARTED
DRAWING N/TOTAL
COMPLETE_PEN_UP
```

That project owns the Marlin long-running streaming policy. `host-ops` may be used for generic serial enumeration/probe when needed, but a hardware-lab live task must not depend on an undeclared `hostops` binary appearing in its PATH.
