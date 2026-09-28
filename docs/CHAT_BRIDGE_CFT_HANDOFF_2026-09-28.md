# Chat Bridge + Host Ops handoff — 2026-09-28

This is a continuation snapshot, not the operating manual. Use `docs/BRIDGE_HOSTOPS_RECOVERY.md` for commands and recovery policy. Always re-read repository heads and daemon status before acting.

## Stable architecture

- Daily Google Chrome is out of scope and must remain untouched.
- Dedicated profile: `~/.local/share/local-agent/chat-bridge-cft`.
- Preferred CfT alias: `~/.local/share/local-agent/chrome-for-testing/current`.
- Rollback profile retained but never selected implicitly: `~/.local/share/local-agent/chat-bridge-chrome`.
- Host Ops owns exact-profile browser lifecycle, CDP inspection and bounded recovery.
- Local Agent helpers are thin Chat Bridge-specific wrappers.
- External recovery is read-only by default; one guarded reload is allowed only for `content_script_missing` or `content_script_stale`.
- `worker_inactive`, `dom_not_ready`, `extension_ambiguous` and `ready` are not reload triggers.

## Final audited baseline

Last code-bearing heads for this work:

- `MichalMatu/host-ops`: `22a3427000b8d159f8975d068d82f4df67274bce`;
- `MichalMatu/local-agent`: `85bb6964134f86840dcc15de76650852d7bb011e`;
- Local Agent daemon: `4.19.2`.

Local Agent `main` may advance with this documentation-only closeout. Current refs remain authoritative.

## Implemented behavior

Host Ops provides generic managed and interactive exact-profile browser sessions. Interactive mode deliberately launches without CDP and without extension flags so the user can complete authentication manually in the same owned profile.

Local Agent exposes:

- `bridge_hostops_session.py start/status/stop` for normal managed mode;
- `login-start/login-status/login-finish` for manual authentication bootstrap;
- `bridge_hostops_recovery.py` for exact-target read-only readiness and one-shot recovery.

`login-finish` clears only Chromium tab/session-restore state. It preserves cookies and account state.

Current composer readiness accepts:

```css
#prompt-textarea,
[data-testid="prompt-textarea"],
div.ProseMirror[contenteditable="true"]
```

## Production evidence

Google authentication succeeded in interactive mode on the same dedicated profile. Login persisted after returning to managed mode.

Latest healthy production evidence before closeout:

```text
PAGE_COUNT=1
CONTENT_SCRIPT_STATE=ready
DOM_READY=True
FINGERPRINT_COUNT=5
WORKER_STATE=inactive
WORKER_ERROR_COUNT=0
MERGED_MAIN_HEALTH=pass
```

The inactive worker is acceptable for Manifest V3.

Final verification:

- Host Ops canonical gate: 716/716 tests PASS, with architecture/design/Ruff/format/mypy/security/dependency checks PASS;
- Local Agent hermetic canonical gate: 494/494 tests PASS, with compile/Ruff/Bridge validation PASS;
- focused Host Ops interactive-session tests: 15/15 PASS;
- focused Local Agent session/recovery tests: 20/20 PASS;
- live branch smoke and merged-main read-only health smoke: PASS.

## Branch hygiene

Merged/superseded browser-recovery candidate branches were removed. Preserve:

- `local-agent/chat-bridge-state` — production runtime-state branch;
- `local-agent/feat/chat-bridge-attachment-inbox` — separate active/unmerged feature work.

The archived, unmerged PR #98 (`fix/chat-bridge-stale-content-refresh`) is discarded during final cleanup rather than merged implicitly.

## Continuation rules

1. Verify current `local-agent/main`, `host-ops/main`, daemon `self_revision`, active tasks and exact profile state.
2. Do not mutate a healthy page.
3. Do not choose among duplicate ChatGPT targets.
4. Do not touch the daily Chrome profile or use broad process killing.
5. Prefer the canonical runbook over historical chat context.
