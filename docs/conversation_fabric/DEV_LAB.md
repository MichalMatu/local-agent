# Conversation Fabric DEV lab

Status: current isolated development/runtime boundary for Conversation Fabric Stage 8.

## Purpose

Conversation Fabric development must not mutate or compete with the installed production Local Agent or the operator's normal Chrome profile.

The DEV lab provides a separate checkout, durable state root and browser profile for synthetic browser tests and the explicitly bounded Stage 8 live-child proof. It does not start a second production Local Agent executor.

## Canonical topology

```text
Production checkout
/Users/michal/local-agent
  branch: main

Development checkout
/Users/michal/local-agent-dev
  branch: develop/conversation-fabric

Primary DEV state root
/Users/michal/Library/Application Support/local-agent-dev/
  lab.json
  state/
  repositories/
  browser-profile/
  logs/
  fixtures/
  node-deps/
```

The checkout and DEV state root are intentionally disjoint so checkout replacement cannot erase durable proof evidence.

## Protected production boundaries

DEV path validation must reject overlap, aliasing or ancestor/descendant collisions with production-owned locations, including:

- `/Users/michal/local-agent`;
- `/Users/michal/Library/Application Support/local-agent`;
- production workspace/state paths;
- production LaunchAgent files/logs;
- the normal Chrome profile root;
- any production Native Messaging registration.

Symlink aliases to protected production paths are also invalid.

## Disabled capabilities

The DEV lab must not become a second production executor/control plane.

Keep these capabilities disabled:

```text
executor_enabled
remote_control_enabled
real_chrome_profile_enabled
native_host_registration_enabled
```

The canonical `local-agent` repository may be execution-enabled in production. The isolated Stage 8 DEV lab remains non-executing because its own executor capability is disabled and the live reasoning-child proof never queues a repository task.

Protected operational branches are not DEV workspaces:

- `chat-bridge-state`
- `operator-control`

## Lab commands

Run from the DEV checkout:

```bash
python -m local_agent.development.lab plan
python -m local_agent.development.lab init
python -m local_agent.development.lab status
```

`plan` is read-only.

`init` may create only the isolated DEV namespace and inert lab directories. It must not switch production Git state, start production supervisors, install/restart LaunchAgents, mutate production operator state, register Native Messaging or touch operational branches.

`status` validates the durable DEV marker and expected layout. Unknown non-empty directories are never silently adopted.

## Browser boundary

Two browser modes are allowed in DEV:

### Synthetic browser tests

Browser smokes use isolated temporary/persistent Chromium profiles with controlled fixtures. They are the normal regression path and may run repeatedly.

### Stage 8 live proof

A real ChatGPT child may be created only by the bounded Stage 8 live flow using a dedicated isolated DEV profile.

Required live sequence:

```text
seed -> prepare -> login -> arm -> run
```

Each invocation performs exactly one authority step. Never auto-chain or automatically retry `run`.

The live flow must not use the operator's normal Chrome profile, production Native Messaging or production Local Agent execution authority.

## Durable evidence rule

Live-state files are proof evidence, not disposable cache.

If an attempt becomes terminal or `ambiguous`:

- do not hand-edit it back to an earlier state;
- do not delete it to make a retry possible;
- do not reuse the same attempt for another live proof.

A later proof must use a fresh isolated DEV live state namespace while preserving the failed namespace as evidence.

The current preserved ambiguous attempt is documented in `docs/CURRENT_HANDOFF.md`.

## Mac operation rule

All Mac-local operations for this project must go through the exact execution target selected for the operation. `host-ops` remains the target for host-level maintenance; repository project work uses that repository's own canonical binding, including `local-agent` self-work when explicitly requested.

Direct GitHub operations remain the normal path for repository inspection and repository-side edits when local execution is unnecessary.

## Stage 8 lab acceptance

Before a live browser effect, confirm:

1. exact `develop/conversation-fabric` SHA;
2. clean DEV checkout;
3. isolated DEV state root/profile;
4. current exact-SHA validation evidence;
5. the isolated DEV executor remains disabled;
6. no production profile or Native Messaging path is involved;
7. the live namespace has no unresolved reused attempt.

The lab boundary is successful when Stage 8 can produce one fresh child proof without altering production paths or granting child execution authority.
