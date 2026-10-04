# Local Agent Operations

This is the canonical operational workflow for `MichalMatu/local-agent`.

## Production/source baseline

```text
Local Agent release line: 4.20.6
immutable tag v4.20.6: 48eb9d8b6c26a9dfb317906d5099acabce8719c8
released Bridge at tag: 0.8.1
current source candidate Bridge: 0.8.2
```

`main` is a moving production source branch and may contain later verified post-release patches. Before any live operation, read fresh daemon status and verify `daemon_version`, `self_revision`, repository registry identity, execution variant and installed Bridge version.

Production bounded-parallel execution uses `agent_parallel.py` with a hard worker cap of four. Serial `agent_multirepo.py` remains fallback, not the production dedupe path.

## Normal inspection order

1. Read `AGENTS.md` and `docs/CURRENT_HANDOFF.md`.
2. Read current `main` and the relevant immutable release/checkpoint SHA.
3. Read fresh daemon status from the operational repository.
4. Read only target repository status/task/result evidence needed for the next decision.
5. For Chat Bridge pacing, read the exact GitHub `conversation_controls` record; never infer scheduling from old chat text.

## Executable repository work

- Resolve the actual target repository from the runtime catalog/registry.
- Require its exact canonical `agent_binding` in `.agent/tasks`.
- Keep executable effects deterministic and bounded.
- Declare required machine/hardware resources explicitly.
- Use one stable branch-scoped `dedupe_key` for one logical intent when overlap is possible.
- Inspect pending/active/recent work before publishing another task.
- Children and Superchat transport never bypass this boundary.

## Multi-repository / host operations

`host-ops` is the explicit `multirepo` host-operation/planning scope. Use it only for host effects that belong there. A repository edit/build/test still belongs to its actual target repository and requires that target repository's own execution-enabled binding.

Never use `host-ops` to tunnel around a disabled target repository.

## Superchat browser model

Production Conversation Fabric runs entirely inside the operator's existing authenticated primary Chrome session and installed Chat Bridge. Parent and child conversations are ordinary tabs in that same browser session.

The supported browser-native path is:

```text
managed parent assistant reply
  -> exact trailing LOCAL_AGENT_CF control block
  -> parent Conversation Fabric content controller
  -> Chat Bridge service worker
  -> existing worker_spawn.js chrome.tabs/chrome.scripting primitives
  -> child tabs
  -> stable child result capture
  -> exact owned-tab cleanup
  -> parent feedback/synthesis
```

Do not launch a second production browser/profile, use `chat-bridge-cft` as the acceptance browser, copy cookies, require a second login, loop on Cloudflare, attach a second production control plane with CDP, or add Native Messaging/browser RPC.

Isolated Chromium remains test-only for deterministic browser/DOM coverage.

## Conversation Fabric controls

A managed parent may emit one exact trailing control block:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"delegate","children":[...]}
LOCAL_AGENT_CF>>>
```

or later:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"collect","campaign_id":"cf-..."}
LOCAL_AGENT_CF>>>
```

The service worker admits controls only from the exact top-frame managed parent. Children are explicitly reasoning-only. Campaign state/dedupe is browser-session scoped, results are bounded and must be stable across repeated observations, and only exact owned child tabs are closed.

## Chat Bridge pacing/control

Conversation Fabric does not use LAB schedule markers for normal pacing. When a child campaign needs another observation:

1. read this parent's exact `conversation_controls` record on `chat-bridge-state`;
2. increment `control_generation`;
3. set `enabled=true` and an exact offset-aware future `next_wake_at`;
4. on the next parent wake emit the exact `LOCAL_AGENT_CF` collect block supplied by the Bridge;
5. when complete, return scheduling to the intended paused state (`enabled=false`, `next_wake_at=null`) unless continued automation is explicitly needed.

Never modify Bridge Master through conversation desired state.

## Live acceptance

After exact-head CI is green and PR `#141` is merged/deployed/reloaded into the normal Chrome session:

1. verify exact source/deployed revision, Bridge `0.8.2`, parent URL/tab and GitHub control state;
2. delegate at least two narrow non-overlapping reasoning jobs from one managed parent;
3. visibly confirm both children open as normal tabs in the same Chrome session without another login/profile;
4. schedule bounded collect wakes only through GitHub control generations;
5. collect stable results and confirm owned child tabs close;
6. parent reconciles results and makes the final decision;
7. if execution is justified, queue exactly one target-bound task with the target repository's canonical binding and stable dedupe key;
8. verify no equivalent duplicate execution;
9. end with the parent scheduling state intentionally paused unless ongoing automation is desired.

Stop rather than weakening checks if parent ownership, child ownership, result identity, repository binding or duplicate-execution status is uncertain.

## Release/checkpoint discipline

- Verify behavior-changing code on the exact candidate SHA before merge.
- Tags remain immutable anchors.
- After merge, allow guarded self-update/deployment to advance naturally and verify exact installed revision.
- Keep only `main`, `chat-bridge-state`, `operator-control` and genuinely active short-lived work branches.
- Historical isolated-browser plans remain evidence only, not normal operating instructions.
