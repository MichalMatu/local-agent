# Local serial operations

`python -m local_agent.host_ops serial transact` provides one bounded raw POSIX serial transaction against an explicitly selected device path below `/dev`.

It is intentionally protocol-agnostic. The caller owns command syntax, line endings, bootloader state and device-specific semantics.

## Examples

Request/response with raw hexadecimal bytes:

```bash
python -m local_agent.host_ops serial transact /dev/cu.usbserial-0001 \
  --baud 115200 \
  --write-hex 4d3131350a \
  --read-limit 4096 \
  --timeout 2 \
  --idle 0.1 \
  --json
```

Some USB-serial devices reset, boot or emit startup bytes when the port is opened. Use `--settle` when the caller needs a bounded delay before input is flushed and the request is sent:

```bash
python -m local_agent.host_ops serial transact /dev/cu.usbserial-0001 \
  --baud 115200 \
  --write-hex 4d3131350d0a \
  --read-limit 4096 \
  --timeout 6 \
  --idle 0.5 \
  --settle 2 \
  --json
```

The settle delay is part of the whole transaction deadline. It defaults to zero and must be shorter than the transaction timeout.

Passive bounded read:

```bash
python -m local_agent.host_ops serial transact /dev/cu.usbserial-0001 \
  --baud 115200 \
  --read-limit 4096 \
  --timeout 2 \
  --idle 0.1 \
  --json
```

Write-only transaction:

```bash
python -m local_agent.host_ops serial transact /dev/cu.usbserial-0001 \
  --baud 115200 \
  --write-text 'PING' \
  --read-limit 0 \
  --timeout 1
```

## Downstream long-running protocols

`serial transact` is a discovery/probe primitive, not a generic replacement for a device-specific session runner.

For a protocol that needs hundreds or thousands of request/acknowledgement cycles, retries/resend policy, device-specific safety state or multi-minute progress, keep that protocol in the downstream project and use host-ops only for genuinely generic host facts when needed. For example, the Anycubic Kobra pen plotter keeps Marlin command validation, homing policy and acknowledged long-running streaming in `hardware-lab/projects/kobra2-neo`; host-ops may enumerate the macOS serial device or perform a small `M115` probe when the port is unknown or ambiguous.

Do not require a downstream worker to have the `hostops` executable in its PATH unless that dependency is explicitly installed and part of that project's contract. Separate Local Agent bindings may have different environments.

Never open a second serial probe against a port that an active downstream physical task already owns.

## Contract

- direct API inputs are type-checked before device lookup/I/O; booleans, non-numeric/non-finite timing values and non-byte payloads fail with controlled validation errors;
- the port must be an absolute path below `/dev` and resolve to a character device;
- baudrate must be a positive integer supported by the host POSIX `termios` implementation;
- transport is configured as raw 8N1 with hardware flow control disabled when the platform exposes that control;
- write payloads are capped at 1 MiB;
- retained reads are capped at 4 MiB;
- the whole transaction deadline is capped at 60 seconds;
- `--settle` is optional, defaults to zero, is bounded by the same transaction deadline and runs after the port is configured but before request I/O;
- after the first received byte, the idle interval may finish the transaction before the whole deadline;
- request/response transactions flush buffered input immediately before writing, after any configured settle delay;
- passive reads do not flush input;
- `--write-text` and `--write-hex` are mutually exclusive;
- the result reports bytes written/read plus deadline, idle and read-limit completion state.

No serial device is selected implicitly. Discovery remains a separate capability (`python -m local_agent.host_ops macos serial` on macOS), and the planner/operator must choose the concrete device path.