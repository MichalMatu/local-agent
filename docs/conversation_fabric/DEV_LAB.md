# Conversation Fabric DEV lab

Status: Stage 3 development boundary. This lab is deliberately **synthetic-only** and does not start a second Local Agent executor.

## Purpose

The production Local Agent must remain usable from `~/local-agent` on `main` while Conversation Fabric / Superchat work is developed separately.

The first DEV boundary therefore isolates only the components needed by current workflow and browser experiments. It does **not** attempt a broad runtime instance refactor before there is evidence that a second executor is required.

## Default topology

```text
PROD checkout
~/local-agent

DEV checkout target
~/local-agent-dev

DEV lab root
~/Library/Application Support/local-agent-dev/
  lab.json
  state/
  repositories/
  browser-profile/
  logs/
  fixtures/
```

The checkout and lab-state root are intentionally disjoint so deleting/recreating a development checkout cannot erase persistent lab evidence.

The lab validator rejects overlap or ancestor/descendant collisions with production identities including:

- `~/local-agent`;
- `~/Library/Application Support/local-agent`;
- `~/agent-workspace`;
- the production LaunchAgent plist;
- production stdout/stderr logs;
- the normal Google Chrome profile root;
- the production Native Messaging manifest.

Canonical path resolution is used before comparison, so a symlink alias to a protected production path is rejected too.

## Capabilities intentionally disabled

The Stage 3 manifest records all of these as false:

```text
executor_enabled
remote_control_enabled
real_chrome_profile_enabled
native_host_registration_enabled
```

`chat-bridge-state` and `operator-control` are explicitly recorded as protected operational branches. The initial lab does not consume them.

This means Stage 3 cannot accidentally become a second production supervisor merely because the development checkout contains the production runtime code.

## Commands

Run from the development checkout:

```bash
python -m local_agent.development.lab plan
python -m local_agent.development.lab init
python -m local_agent.development.lab status
```

`plan` is read-only and prints the exact namespace that would be used.

`init` creates only the lab root, marker and inert subdirectories. It does **not**:

- clone or switch a Git checkout;
- create/provision repository control worktrees;
- start `agentd`, `agent_parallel.py` or the guarded entrypoint;
- install or restart a LaunchAgent;
- modify production disable/operator state;
- register a Chrome Native Messaging host;
- launch normal Chrome;
- touch `chat-bridge-state`, `operator-control` or any project `agent-control` branch.

`status` verifies the durable marker and required lab directories. An existing non-empty directory without the exact marker is never silently adopted.

For tests or disposable experiments, all locations can be overridden explicitly:

```bash
python -m local_agent.development.lab plan \
  --home /tmp/example-home \
  --root /tmp/example-lab \
  --checkout /tmp/example-checkout \
  --production-checkout /tmp/example-production
```

The same overlap checks apply to overrides.

## Browser boundary

The existing Chromium bridge smoke already uses a temporary persistent profile, forces the context offline and routes only a synthetic ChatGPT fixture. That remains the preferred browser test model for the next phases.

The persistent `browser-profile/` directory in this lab is reserved for later synthetic spawn/restart tests that need state across controlled process restarts. It must not point at the operator's normal Chrome data directory.

No real ChatGPT child creation belongs in Stage 3.

## Why there is no second executor yet

Several production owners still derive mutable paths at module load from the normal home directory, including daemon state/lock paths and local operator state. macOS launchd also has one production label/log contract, and the Native Messaging installer uses the normal Chrome registration directory.

Refactoring all of those owners into an instance namespace would be a broad runtime change. The current Conversation Fabric phases do not need that risk: workflow tests use disposable repositories and browser proof can use synthetic Chromium.

If a later campaign integration phase genuinely needs concurrent real execution, add an explicit instance namespace as its own scoped milestone. That future design must cover at least:

- daemon/global state root and lock;
- repository registry and workspaces;
- operator disable/install state;
- logs;
- LaunchAgent label/plist;
- Native Messaging host name/manifest/wrapper;
- browser profile and extension identity;
- remote control/state branch identities.

It must preserve existing production defaults exactly.

## Stage 3 exit criteria

Stage 3 is complete when:

1. the DEV layout and collision checks are deterministic and fully tested;
2. initialization is idempotent and refuses ambiguous pre-existing state;
3. tests prove DEV cannot resolve to protected PROD paths, including symlink aliases;
4. no production runtime entrypoint imports or starts the development lab;
5. the documented synthetic browser path remains independent of normal Chrome;
6. CI is green on the exact candidate branch;
7. the verified change is merged to `develop/conversation-fabric` without touching `main`, `chat-bridge-state` or `operator-control`.
