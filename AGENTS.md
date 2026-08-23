# Local Agent repository rules

This repository is paired by default with `MichalMatu/esp32s3_LiteGraph`. In a future session, if the user provides this repository or says to use the established local-agent flow, read `SESSION_BOOTSTRAP.md` first and treat ESP32 LiteGraph as the default development target unless the user explicitly asks to work on the daemon itself.

This repository is infrastructure. Prefer deterministic behavior, bounded execution and explicit failure over clever recovery.

- **English-only execution contract:** every machine-generated artifact and every line that can reach daemon/task logs must be English. This includes agent/Codex progress narration, final task summaries, source code, comments, identifiers, UI strings, runtime log messages, test names/descriptions, documentation, prompts, task titles/descriptions, shell-visible status text, and commit messages. Do not emit Polish or any other non-English prose in execution output unless a task explicitly requires localized user-facing content.
- Repository/task language requirements apply independently from the language used in the interactive ChatGPT conversation. A user may converse in Polish while all local-agent/Codex execution output remains English.
- Every newly authored Codex prompt must restate the English-only execution contract near the top so the requirement survives repository-context or instruction changes.
- `agentd.py` owns queue orchestration, durable claims, remote status/control and self-update.
- `agent_core.py` owns deterministic task execution and result publication.
- `agent_runtime.py` adds command process-group lifecycle, idle/task watchdogs and progress events without changing the target repository.
- `agentctl.py` is diagnostics only; the daemon must not depend on it.
- `local-agent` has a legacy task contract. Do not assume fields supported by `DeterministicRunner` are implemented here merely because the names look compatible.
- `expected_head` is not implemented by `local-agent`. If exact source identity matters, verify the expected Git SHA explicitly in an early task command before later side effects.
- Identical command strings within one task may reuse the earlier result through `agent_core.run_command_list`. Do not rely on repeating an identical string to force re-execution; use a new task when a true rerun is required.
- Never automatically replay a task after a daemon/process interruption.
- Never silently reuse a task id for a different payload.
- Never remove or weaken command, idle or whole-task watchdogs without explicit justification.
- All daemon self-updates must validate before restart and roll back on failure.
- Do not add a local coding LLM to the deterministic execution path.
- Keep Git staging path-exact; never use `git add -A` in publication logic.
- Preserve ignored build caches unless a task explicitly asks for a clean rebuild.
- Never destroy a dirty disposable workspace without first creating a recoverable workspace checkpoint outside the worktree; if checkpointing fails, skip destructive cleanup.
- Treat `~/agent-workspace/control` as daemon execution infrastructure. Queue tasks/control requests through the remote `agent-control` branch via GitHub/API tooling or another trusted writer checkout rather than manually authoring them in the daemon control clone during normal operation.
- Target-project verification is impact-driven: queue only tests/builds that exercise code, configuration, dependencies or integration boundaries plausibly affected by the current diff.
- Do not run a broad regression suite merely because it exists or as a default end-of-iteration gate. A broad suite requires a concrete impact rationale: shared/cross-cutting infrastructure changed, dependency impact cannot be bounded confidently, the target repository explicitly requires it for this change class, or the user explicitly requests it.
- After a focused fix, rerun only the affected gate unless that fix expands the impact surface. Previously green evidence remains valid while the code and relevant dependencies covered by that gate have not changed.
- New control/progress behavior requires unit coverage.
- Long multi-phase tasks must prefer structured sequential `steps` with meaningful
  English stage names. Do not conceal a safely splittable build/flash/test/stress/
  reboot workflow in one opaque command; intentionally long scripts should emit
  periodic `[AGENT_PROGRESS] ` JSON markers. Local heartbeats are about 30 seconds
  and remote run/daemon progress is normally refreshed about every 60 seconds.
- Heartbeat telemetry is best-effort and may include host CPU/load/memory/swap plus
  active process-group CPU/RSS/child counts; unavailable metrics are omitted.
- Before publishing daemon changes run `python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py` and `python -m unittest discover -q`.

## Golden-standard reference

Read `GOLDEN_STANDARD.md` for the current versioned infrastructure invariants and audit disposition. Source publication and ESP32 hardware flashing are separate gates; never infer the running firmware commit from repository `main` or semantic firmware version alone.

### Invalid task contract

Malformed task JSON is a terminal queue error, not a retry candidate. The daemon publishes `failure_reason=invalid_task_file` under the filename rejection key, and pending scans check that rejection before parsing so a bad task cannot spam every poll forever. Valid historical filename aliases/prefixes may differ from `task.id`; execution results and claims remain keyed by `task.id`.
