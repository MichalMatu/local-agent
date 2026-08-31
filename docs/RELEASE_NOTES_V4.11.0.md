# local-agent v4.11.0

v4.11.0 promotes the resource-aware multi-repository supervisor from staging into the normal `main` release flow.

## Highlights

- adds `agent_parallel.py` and `agent_parallel_worker.py`;
- recommended production setting: `--max-workers 2`;
- retains `agent_multirepo.py` as the direct serial fallback;
- keeps one shared daemon lock so serial and parallel supervisors cannot run together;
- preserves repository-scoped claims, runs, results, workspaces and inherited repository leases;
- adds conservative machine/named-resource arbitration with inherited lock descriptors;
- keeps unknown/legacy tasks machine-exclusive by default;
- allows clearly software-only tasks to opt into overlap with `resources: []` and an enabled `memory_limit_mb <= 1024`;
- adds machine-task priority/drain fairness and bounded one-shot contention handling;
- prevents global restart/status/self-update from racing active workers;
- improves silent Git/self-update failure diagnostics;
- adds production macOS LaunchAgent template `deploy/macos/com.michal.local-agent.parallel.plist`.

## Validation

The release candidate passed Linux compile/Ruff/full unit/integration CI and macOS process/multi-repository/parallel smoke on the exact candidate. Real Mac smoke additionally proved both:

- temporal overlap of two software-only tasks in different repositories;
- zero overlap between a full-machine task and another repository task.

## Release flow

Production runs from `~/local-agent` on `main`. `v*-staging` branches/worktrees are temporary candidate-validation infrastructure only. After this release is verified live from `main`, tag the released commit `v4.11.0` and remove the obsolete v4.11 staging worktree/branch.

## Downstream planner documentation

The Local Agent workflow/resource contract was synchronized with the registered repositories:

- `MichalMatu/esp32s3_LiteGraph`;
- `MichalMatu/growbox-ml-controller` (`main` and active `mvp/environment-controller` workflow instructions);
- `MichalMatu/MatrixHub` (`main` and `develop`).

Future planner-facing Local Agent contract changes require the same downstream documentation audit before release.

## Rollback

Stop the parallel LaunchAgent, restore the serial LaunchAgent configuration and start `agent_multirepo.py`. No repository-control/workspace migration is required.
