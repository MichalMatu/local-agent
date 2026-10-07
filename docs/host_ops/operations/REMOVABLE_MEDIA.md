# Removable-media artifact deployment

## Purpose

`python -m local_agent.host_ops macos deploy-media` is a deterministic workflow that composes existing macOS storage inspection/control with verified local artifact deployment. It is intended for USB/SD-style removable volumes where Local Agent already knows the exact `diskNsN` volume identifier.

```bash
python -m local_agent.host_ops macos deploy-media disk4s1 ./firmware.bin --name firmware.bin --json
python -m local_agent.host_ops macos deploy-media disk4s1 ./firmware.bin --name firmware.bin --replace --eject --json
```

## Contract

The workflow inventories the exact external volume, validates external/read-write state, mounts only
when needed, re-inspects after mount, deploys through LocalArtifactDeployer, and optionally ejects
the containing whole disk only after verified deployment.

One monotonic workflow deadline spans inspect, optional mount, re-inspection, artifact deployment
and optional eject. Every stage receives only the remaining budget.

There is no automatic eject after deployment failure. Structured failures preserve stage,
mounted_by_workflow, artifact_committed and storage_action_attempted evidence. A timeout after a
side effect therefore cannot be rendered as a false clean failure.

## Non-goals

The workflow does not choose a disk or partition, format/partition media, infer a firmware filename, erase unrelated files, or decide which artifact a project should deploy. Those choices remain explicit caller/project policy.
