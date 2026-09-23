# Local Agent v4.13.0

## Resource admission

- Task `resources` is now mandatory and strictly validated; invalid declarations fail explicitly instead of silently falling back to whole-machine exclusivity.
- `resources: []` means no exclusive external resource beyond the repository lease, so independent repository builds/tests may overlap.
- Named resources serialize only concrete shared devices or external state. `machine` is reserved for genuine whole-host operations.
- `memory_limit_mb` is independent from resource admission; the old 1024 MiB parallel-admission rule is removed.
- Resource contention is durable waiting with bounded retry and published `waiting_resource` status.

## Chat Bridge liveness

- `NEXT=<duration>` now arms or re-arms the emitting conversation before scheduling its one-shot wake.
- `NEXT` does not override the global master switch or persistent interval.
- Planner guidance now treats unfinished work and resource waiting as continuation states that end with `NEXT`, never `STOP`.

## Verification

- Added explicit task-resource contract coverage.
- Added real wait/release/retry resource tests and expanded macOS smoke coverage.
- Added Chat Bridge regression coverage for `PAUSE -> NEXT -> enabled + scheduled`.

