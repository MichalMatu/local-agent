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
