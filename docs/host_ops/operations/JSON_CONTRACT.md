# Machine-readable JSON contract

`host-ops` exposes structured JSON from command-specific `--json` flags. Existing commands intentionally keep their established top-level JSON shapes; this contract version exists so callers such as Local Agent can negotiate compatibility without wrapping or rewriting those outputs.

## Discovering the contract version

```bash
python -m local_agent.host_ops --json-contract-version
```

Current output:

```text
1
```

The command prints only the decimal contract version followed by a newline and exits with status 0. It does not require host configuration or external tools.

## Versioning policy

Contract version `1` covers the current machine-readable CLI output shapes.

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
