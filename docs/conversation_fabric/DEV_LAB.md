# Conversation Fabric DEV lab

> **HISTORICAL / RETIRED PRODUCTION PATH**
>
> This document records the isolated Stage 8 development lab that predated the accepted same-browser Conversation Fabric architecture. Do not use it as current production operating guidance. Production child delegation now uses ordinary tabs in the operator's already authenticated primary Chrome session. Current guidance is in `README.md`, `CURRENT_PLAN.md`, `NEXT_CHAT_PROMPT.md`, `../CURRENT_HANDOFF.md` and `../GOLDEN_STANDARD.md`.

Status: retained development/test evidence only.

## Historical purpose

Conversation Fabric development originally isolated browser proof work from the installed production Local Agent and the operator's normal Chrome profile.

The DEV lab provided a separate checkout, durable state root and browser profile for synthetic browser tests and the explicitly bounded Stage 8 live-child proof. It never represented a second production Local Agent executor.

## Historical topology

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

The checkout and DEV state root were intentionally disjoint so checkout replacement could not erase durable proof evidence.

## Protected production boundaries

DEV path validation rejected overlap, aliasing or ancestor/descendant collisions with production-owned locations, including:

- `/Users/michal/local-agent`;
- `/Users/michal/Library/Application Support/local-agent`;
- production workspace/state paths;
- production LaunchAgent files/logs;
- the normal Chrome profile root;
- any production Native Messaging registration.

Symlink aliases to protected production paths were also invalid.

## Disabled capabilities

The DEV lab was never allowed to become a second production executor/control plane.

These capabilities stayed disabled:

```text
executor_enabled
remote_control_enabled
real_chrome_profile_enabled
native_host_registration_enabled
```

The canonical `local-agent` repository may be execution-enabled in production. The isolated Stage 8 DEV lab remained non-executing because its own executor capability was disabled and its live reasoning-child proof never queued a repository task.

Protected operational branches were not DEV workspaces:

- `chat-bridge-state`
- `operator-control`

## Historical lab commands

The retired DEV checkout used:

```bash
python -m local_agent.development.lab plan
python -m local_agent.development.lab init
python -m local_agent.development.lab status
```

`plan` was read-only. `init` created only the isolated DEV namespace and inert lab directories. `status` validated the durable DEV marker and expected layout.

These commands may remain useful for regression archaeology, but they are not prerequisites for current production Conversation Fabric acceptance.

## Retired browser boundary

Two browser modes existed in the DEV phase:

### Synthetic browser tests

Browser smokes used isolated temporary/persistent Chromium profiles with controlled fixtures. This remains valid for deterministic CI/test coverage.

### Stage 8 isolated live proof

The historical real ChatGPT child proof used a dedicated isolated DEV profile and the sequence:

```text
seed -> prepare -> login -> arm -> run
```

That live path is retired. Current production acceptance must use the already authenticated primary Chrome session and installed Chat Bridge; isolated login/Cloudflare state is not a production dependency.

## Durable evidence rule

Historical live-state files remain proof evidence, not disposable cache. Terminal or ambiguous attempts should not be rewritten or deleted merely to manufacture a passing historical proof.

## Current Mac-operation rule

Current machine work follows target authority, not this retired lab topology:

- use direct GitHub edits for exact repository/source/docs changes when CI is sufficient;
- use Local Agent only when machine-local commands/builds/tests/devices/host state are genuinely required;
- resolve the actual target through the canonical runtime catalog, require `execution_enabled=true`, and use the exact canonical target binding;
- Conversation Fabric children remain reasoning-only.

## Current production replacement

For current Conversation Fabric work, read:

1. `../CURRENT_HANDOFF.md`
2. `../GOLDEN_STANDARD.md`
3. `README.md`
4. `CURRENT_PLAN.md`
5. `NEXT_CHAT_PROMPT.md`

The accepted architecture is same-browser, durable in `chrome.storage.local`, worker-polled through the existing GitHub-control alarm, exact-ownership recovered after restart, and terminal-feedback at-most-once.
