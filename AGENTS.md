# Local Agent repository rules

This repository is paired by default with `MichalMatu/esp32s3_LiteGraph`. In a future session, if the user provides this repository or says to use the established local-agent flow, read `SESSION_BOOTSTRAP.md` first and treat ESP32 LiteGraph as the default development target unless the user explicitly asks to work on the daemon itself.

This repository is infrastructure. Prefer deterministic behavior, bounded execution and explicit failure over clever recovery.

- `agentd.py` owns queue orchestration, durable claims, remote status/control and self-update.
- `agent_core.py` owns deterministic task execution and result publication.
- `agent_runtime.py` adds command process-group lifecycle, idle/task watchdogs and progress events without changing the target repository.
- `agentctl.py` is diagnostics only; the daemon must not depend on it.
- Never automatically replay a task after a daemon/process interruption.
- Never silently reuse a task id for a different payload.
- Never remove or weaken command, idle or whole-task watchdogs without explicit justification.
- All daemon self-updates must validate before restart and roll back on failure.
- Do not add a local coding LLM to the deterministic execution path.
- Keep Git staging path-exact; never use `git add -A` in publication logic.
- Preserve ignored build caches unless a task explicitly asks for a clean rebuild.
- New control/progress behavior requires unit coverage.
- Before publishing daemon changes run `python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py` and `python -m unittest discover -q`.

## Golden-standard reference

Read `GOLDEN_STANDARD.md` for the final infrastructure invariants and audit disposition. Source publication and ESP32 hardware flashing are separate gates; never infer the running firmware commit from repository `main` or semantic firmware version alone.

### Invalid task contract

Malformed task JSON is a terminal queue error, not a retry candidate. The daemon publishes `failure_reason=invalid_task_file` under the filename rejection key, and pending scans check that rejection before parsing so a bad task cannot spam every poll forever. Valid historical filename aliases/prefixes may differ from `task.id`; execution results and claims remain keyed by `task.id`.
