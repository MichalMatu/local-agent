# local-agent v4.11.2

v4.11.2 is a planner/documentation contract alignment patch for the v4.11 bounded-parallel release line.

## Changes

- corrects the autonomous Chat Bridge contract so one conversation follows one active task for its goal without falsely claiming global executor concurrency is one;
- records that unrelated repositories/conversations may overlap when resource admission permits it;
- updates the machine-specific Mac bootstrap to the current three-repository registry layout under `~/agent-workspace/repos/<repository-id>/`;
- records the loaded bounded-parallel LaunchAgent topology (`agent_parallel.py --max-workers 2`) and the production `deploy/macos/com.michal.local-agent.parallel.plist` template;
- synchronizes LiteGraph planner documentation so its workspace paths and Chat Bridge/autopilot behavior match the canonical Local Agent contract;
- does not change task schema, resource arbitration, scheduler behavior, execution leases, watchdogs or serial fallback behavior.

This patch intentionally bumps `RELEASE_VERSION` so production `main`, the installed daemon revision/version and the immutable release tag remain aligned after the canonical documentation correction.
