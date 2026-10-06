# Absorbed Host Ops tooling

Host Ops is now an internal deterministic capability subsystem of Local Agent.

Source baseline imported by PR #176:

```text
donor: MichalMatu/host-ops
donor main: b12b6f33a5ee667201d4bddcbfa3cb1d1cb2948b
runtime namespace: local_agent.host_ops
machine-readable JSON contract: 1
```

Local Agent remains the only planner/orchestrator. The absorbed subsystem validates inputs, performs bounded host/remote effects and returns structured evidence; it does not own repository routing, scheduling, task admission, Conversation Fabric policy or daemon lifecycle.

## Command surface

Invoke the absorbed CLI from the Local Agent checkout with:

```bash
python -m local_agent.host_ops --json-contract-version
python -m local_agent.host_ops doctor --json
python -m local_agent.host_ops host profile --json
```

Machine-local configuration intentionally remains compatible with the donor layout, including `~/.config/host-ops/config.toml` and `HOST_OPS_CONFIG`.

The standalone `MichalMatu/host-ops` repository and binding are transitional compatibility only until live cutover is complete. New host-maintenance task preparation targets `local-agent`.

Reusable donor documentation is preserved below `docs/host_ops/`. The old standalone Local Agent onboarding document is intentionally not imported because repository identity/control-plane onboarding is no longer part of Host Ops ownership.
