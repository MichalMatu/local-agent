# Local tool inspection

`python -m local_agent.host_ops tools inspect` reports deterministic local executable presence and bounded version evidence for explicitly named tools.

## Contract

```bash
python -m local_agent.host_ops tools inspect python3 git cmake ninja arm-none-eabi-gcc pio --json
```

Each requested executable basename is resolved through the current `PATH`. The result reports:

- requested tool name;
- whether it is present;
- resolved real path when present;
- the first non-empty line produced by a bounded `--version` probe;
- version-probe exit code;
- normalized probe error when the executable exists but version evidence is incomplete.

Missing tools are normal inspection results and do not fail the whole command. Invalid names fail before process creation. Names are restricted to executable basenames and a single call is capped at 64 unique tools.

## Bounds

The default version probe uses the shared `ProcessRunner` with:

- 5 second whole-process timeout;
- 8 KiB retained stdout;
- 8 KiB retained stderr;
- argv execution only, with no shell interpolation.

The capability does not install packages, mutate `PATH`, select a build target, infer project requirements, or schedule work. Tool-specific commands beyond the generic `--version` probe remain project/caller policy.

## Evidence semantics

A present executable can still return a non-zero version exit code, time out, or truncate output. Those cases stay visible in the structured result instead of being promoted to successful version evidence.

This capability is intended for preflight checks before a planner dispatches build or device work. It is not a package manager or toolchain bootstrapper.
