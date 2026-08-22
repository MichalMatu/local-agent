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
