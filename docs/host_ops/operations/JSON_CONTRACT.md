# Machine-readable JSON contract

`host-ops` exposes structured JSON from command-specific `--json` flags. Existing commands intentionally keep their established top-level JSON shapes; this contract version exists so callers such as Local Agent can negotiate compatibility without wrapping or rewriting those outputs.

## Discovering the contract version

```bash
python -m local_agent.host_ops --json-contract-version
```

Current output:

```text
2
```

The command prints only the decimal contract version followed by a newline and exits with status 0. It does not require host configuration or external tools.

## Version 2 migration

Version 2 makes one semantic correction without introducing a common JSON envelope:

- remote-Git prepare/run result field ok now means the workflow is trustworthy: the underlying
  process completed successfully and the exact readiness marker for the requested workspace/revision
  was observed;
- under version 1, a process exit code of zero without readiness evidence could emit ok=true while
  the CLI correctly exited with status 1; version 2 removes that contradiction;
- prepared remains explicit, the nested process object is unchanged, and all command-specific
  top-level JSON shapes remain unchanged.

Consumers that used remote-Git result ok must negotiate contract version 2 before relying on this
corrected meaning. Consumers that only use other command shapes are unaffected by the migration.

## Frozen command-family matrix

Version 2 intentionally preserves command-specific top-level shapes. Callers consume the family
they invoked rather than assume one common envelope.

| Case | Machine-readable behavior | Exit |
| --- | --- | ---: |
| normal command success | command-specific object or array on stdout | 0 |
| ADB/macOS/artifact/browser runtime failure | error object on stderr | 1 |
| ADB verified transfer failure | error plus action_attempted, committed and cleanup_failed on stderr | 1 |
| SSH/remote-Git input validation | ok=false error object on stdout | 2 |
| SSH verified transfer failure | ok=false error plus action_attempted, committed and cleanup_failed on stderr | 1 |
| removable-media partial failure | stage/effect object on stderr with artifact_committed and storage_action_attempted | 1 |
| network probe failure | normal network result object with ok=false on stdout | 1 |
| SSH exec / remote-Git process result | process-bearing object on stdout | mapped process exit; remote-Git missing readiness is 1 |
| bounded serial deadline | normal serial result with deadline_reached=true on stdout | 0 |
| argparse rejection before command dispatch | argparse text on stderr; no JSON envelope is promised | 2 |

Transfer effect fields are conservative. action_attempted means a mutating transfer or commit
started. committed is true only after the destination is known to have crossed its commit point.
cleanup_failed means cleanup of unique staging could not be confirmed. An ambiguous timeout during
rename, move or link must not be promoted to committed=true without positive evidence.

Parser-level argparse failures remain outside the command JSON boundary in version 2. Making them
JSON-aware, changing stdout/stderr ownership, or introducing a common envelope requires a future
versioned migration.

## Versioning policy

Contract version `2` covers the current machine-readable CLI output shapes.

The version remains unchanged for backwards-compatible changes, including:

- adding new commands;
- adding optional fields when existing consumers can ignore unknown fields;
- adding new enum/status values only where the documented contract already permits extensible values;
- changing human-oriented text output without changing `--json` output.

The version must increase before an incompatible machine-readable change is merged, including:

- changing a command's top-level JSON type or envelope;
- removing or renaming an existing field;
- changing an existing field's meaning or JSON type incompatibly;
- changing exit-status semantics in a way that breaks machine consumers.

A contract-version bump requires an explicit migration note and compatibility review. Do not silently add a common envelope around existing `--json` commands merely to carry the version; callers should query the top-level version flag before consuming command-specific JSON.
