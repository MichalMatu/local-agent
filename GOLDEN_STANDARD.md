# Local Agent Golden Standard v4.3

This is the final infrastructure audit summary for the `MichalMatu/local-agent` + `MichalMatu/esp32s3_LiteGraph` pair. Operational details remain canonical in `SESSION_BOOTSTRAP.md`.

## Invariants

- `agentd.py` is the only daemon entry point.
- The daemon is a deterministic executor, never a coding model.
- All machine-generated execution content is English-only, including Codex/agent progress narration, task summaries, source code, comments, UI/runtime strings, tests, documentation, prompts, shell-visible status messages, and commit messages. Interactive ChatGPT conversation language is independent from this execution-language contract.
- Every newly authored Codex prompt restates the English-only execution requirement near the top.
- One OS-locked daemon instance is allowed.
- Every task has an immutable payload digest and one durable attempt claim.
- A claimed, interrupted, or corrupt-claim task is never automatically replayed.
- Corrupt durable claims are converted to a terminal `corrupt_claim_state` result for a known queued task and quarantined for evidence.
- Malformed task JSON is a terminal `invalid_task_file` failure; it is never retried and may not spam every poll forever. Historical filename aliases/prefixes that differ from `task.id` remain valid.
- Command, no-output, and whole-task watchdogs are mandatory.
- SIGTERM/SIGINT terminate the active process group.
- Result publication may be retried, execution may not.
- Self-update is allowed only from a clean `local-agent/main` checkout, accepts fast-forward updates only, validates locally, rolls back failures, then restarts by `exec`.
- The live daemon checkout is never mutated to prepare a daemon release. Release staging happens in a separate temporary clone.
- The ESP32 user checkout is never reset or cleaned by the daemon. Work happens in `~/agent-workspace/work`.
- Progress/status/results are remotely observable on `esp32s3_LiteGraph/agent-control`.
- Target-project verification is impact-driven. Tests that have no realistic path to detecting a regression from the current diff are not queued merely for completeness.
- Broad regression suites are opt-in rather than default final gates; they require a cross-cutting change, uncertain dependency blast radius, an explicit target-repository requirement for the change class, or an explicit user request.
- Green targeted evidence may be reused while the code and relevant dependencies covered by that evidence remain unchanged.
- Secrets never belong in GitHub tasks, results, runs, logs committed to control, or repository documentation.

## ESP32 product workflow

Default product target is `MichalMatu/esp32s3_LiteGraph/main`. `local-agent` is infrastructure unless explicitly requested otherwise.

Normal loop: inspect source/rules -> focused patch -> impact-matched focused tests -> only justified broader gates -> exact diff review -> publish target source -> hardware flash when required -> bounded serial capture -> authenticated API/log-tail smoke -> final evidence.

`pio run -c platformio.tests.ini -e test-all-host` is available as a broad ESP32 regression gate, but it is not a mandatory per-iteration or per-feature gate. Unrelated subsystem suites should not run when the current diff cannot plausibly affect them.

Publishing source is not the same as flashing hardware. Never state that the bench contains a source commit merely because `main` contains it or because the device reports semantic version `0.6.0`. Hardware validation of a new firmware commit requires an explicit successful upload or an exact build-identity mechanism that proves the running source revision.

Current bench base URL is `http://192.168.0.21`. The serial port must be rediscovered immediately before upload/monitor. Existing observed adapter VID:PID is `1A86:7523`; the observed path `/dev/cu.usbserial-110` is not a permanent identifier.

For future ESP32 work, adding an exact firmware source/build revision to `/rest/features` or `/rest/systemStatus` is desirable because it lets ChatGPT prove which commit is actually running after a flash.

## Required daemon release gate

For non-trivial daemon changes:

1. create a fresh temporary clone from current `local-agent/main` and create/update `v*-staging` there; never checkout staging in the live `~/local-agent` daemon directory;
2. make deterministic source/test/doc changes in that isolated clone;
3. run `python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py`;
4. run `python -m unittest discover -q`;
5. review the exact staged diff and paths;
6. push the staging SHA and require green GitHub CI on that exact SHA;
7. fast-forward `main` to exactly the validated SHA, never force it;
8. let the idle daemon self-update from `main`;
9. verify remote `daemon_version` and `self_revision`;
10. run one real queue smoke task through `agent-control` and require a terminal green result.

## Audit disposition

The v4.2 audit:

- removed obsolete `agent_OLD.py`;
- removed the unused v2 daemon loop from `agent_core.py` so `agentd.py` is the only daemon entry point;
- hardened self-update to require a clean `main` checkout;
- added terminal recovery/quarantine for corrupt durable claims;
- added terminal handling for malformed task files while preserving historical filename aliases;
- preserved command, idle and whole-task watchdogs plus process-group termination;
- added structured sequential stages, bounded domain progress markers, 30-second local
  heartbeats, 60-second active-command remote publication, and best-effort telemetry;
- formalized isolated release staging and the distinction between published ESP32 source and flashed/running firmware;
- formalized impact-driven verification so broad test suites are not rerun without a concrete regression-detection rationale;
- formalized English-only machine-generated execution output independently from the user's conversational language.

## Invalid task contract

Malformed task JSON is a terminal queue error, not a retry candidate. The daemon publishes `failure_reason=invalid_task_file` under the filename rejection key, and pending scans check that rejection before parsing so a bad task cannot spam every poll forever. Valid historical filename aliases/prefixes may differ from `task.id`; execution results and claims remain keyed by `task.id`.
