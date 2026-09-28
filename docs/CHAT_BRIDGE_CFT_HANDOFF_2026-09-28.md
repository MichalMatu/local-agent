# Chat Bridge + Host Ops handoff — 2026-09-28

This document is the continuation point for the Chat Bridge / Host Ops browser-recovery work. Read this before changing code or running recovery.

## Repositories and exact known-good heads

- `MichalMatu/local-agent`
  - `main`: `7dde1349c610e9d6c0aea1e7a890d3309e1134ce`
  - merge: PR #102, `Use Chrome for Testing for managed Chat Bridge sessions`
  - production daemon self-updated to this exact revision during the final verification cycle
  - daemon version remains `4.19.1`
- `MichalMatu/host-ops`
  - `main`: `49592183b5edf83dd1a74d492fd2439ab2ae4361`
  - this includes managed browser sessions, readiness diagnostics, bounded content-script recovery and macOS Chrome for Testing process discovery

Do not assume these SHAs are still current in a later session. Re-read both `main` refs first and compare before changing anything.

## What is implemented

### Host Ops browser capability chain

The current browser flow is intentionally split into bounded generic capabilities:

1. browser/process discovery;
2. exact CDP target inventory;
3. read-only snapshot / selector-count evidence;
4. extension/service-worker diagnostics;
5. exact-page readiness classification using DOM selectors and content-script SHA-256 fingerprints;
6. bounded content-script recovery: readiness -> at most one guarded reload -> readiness re-check;
7. managed browser session lifecycle: dedicated profile `start / status / stop`, dynamic loopback CDP, no adoption of the normal browser profile;
8. macOS Chrome for Testing root-process discovery.

Important safety properties:

- no implicit attach to the normal daily Chrome profile;
- no `Runtime.evaluate` in readiness/recovery;
- no arbitrary JS, click, fill or worker mutation;
- no reload loop;
- mutation is allowed only for `content_script_missing` or `content_script_stale`;
- `dom_not_ready`, `extension_ambiguous`, `worker_inactive` and `ready` do not trigger page mutation;
- Host Ops owns browser process lifecycle; Local Agent wrappers do not implement another process manager.

### Local Agent integration

`local-agent` now contains:

- `scripts/bridge_hostops_session.py`
  - thin Chat Bridge wrapper over `hostops browser session`;
  - `start / status / stop`;
  - always uses the current unpacked `chat_bridge/` directory;
  - fail-closed on the standard macOS branded Google Chrome executable;
  - Chrome for Testing and Chromium remain supported.
- `scripts/bridge_hostops_recovery.py`
  - accepts either explicit `--endpoint` or exact managed `--profile-dir`;
  - derives expected Bridge script fingerprints from the current manifest/files;
  - resolves profile -> loopback endpoint via Host Ops;
  - requires exactly one matching ChatGPT page target;
  - read-only by default;
  - `--recover` delegates the one-shot mutation to Host Ops C4.

The Bridge's own native recovery remains preferred whenever the Bridge still answers its protocol. External Host Ops recovery is a fallback, not a replacement for `RELOAD=CONTENT` / `RELOAD=BRIDGE` or Bridge-owned content-script probing/reinjection.

## Browser runtime decision

Do not use the normal branded Google Chrome application for automatic unpacked-extension loading on current Chrome releases.

The dedicated Bridge runtime is Chrome for Testing (CfT):

- installed privately under `~/.local/share/local-agent/chrome-for-testing/153.0.8010.36/`;
- stable alias: `~/.local/share/local-agent/chrome-for-testing/current`;
- expected binary:
  `~/.local/share/local-agent/chrome-for-testing/current/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
- production managed profile:
  `~/.local/share/local-agent/chat-bridge-cft`;
- old branded-Chrome profile is retained only as rollback data:
  `~/.local/share/local-agent/chat-bridge-chrome`.

The old branded profile was stopped after the CfT cutover. Do not delete it during initial continuation work.

## Verified runtime behavior

A real CfT smoke on macOS confirmed:

- managed session start/status/stop works with the dedicated profile;
- dynamic CDP is loopback-only;
- all five current Chat Bridge content scripts were `matched` by readiness;
- content-script state was `ready`;
- service worker was running with `error_count=0` during the successful smoke;
- the old branded-Chrome profile was stopped after the successful cutover.

The dedicated profile intentionally persists across restarts so ChatGPT login state can be retained.

## Verification evidence and known flake

### Local Agent C8

Before merge, on exact head `473e266f4cbbfd068e6a50474a1d2a514afaf543`:

- focused `bridge_hostops_session` tests: 8/8 PASS;
- canonical `scripts/verify.py`: PASS;
- Python unit/integration suite: 476/476 PASS;
- Bridge JS syntax/tests and JSON validation: PASS;
- Ruff/compile stages: PASS.

PR #102 merged to `7dde1349c610e9d6c0aea1e7a890d3309e1134ce`.
The merge commit tree is exactly the same tree as the fully verified feature head.

Two later full post-merge runs failed only on the same unrelated timing-sensitive integration test:

`tests.test_control_probe_parallel_admission.ControlProbeParallelAdmissionIntegrationTests.test_running_control_repository_does_not_drain_unrelated_admission`

That test uses a short 4-second admission window. The exact same test on the exact merge SHA was then run in isolation three times and passed 3/3. Do not change C8/browser code because of this known timing flake unless new evidence connects the failure to the browser work.

### Host Ops C5.1

The Chrome for Testing process-discovery fix was verified before and after merge with the canonical Host Ops gate. The suite had 699/699 tests passing on the exact C5.1 merge path, plus a real CfT managed-session smoke.

## Current continuation point

The last read-only production health check did not find a page target: the managed CfT process/CDP was alive but `attach inspect` returned `page_count=0`.

This is not evidence that the extension is broken. The likely state is simply that the last CfT window/tab was closed while the browser process remained alive.

The next session must re-check this from scratch; do not assume `page_count=0` is still true.

### Next action, in order

1. Re-read current `local-agent/main` and `host-ops/main`; verify no drift before code changes.
2. Read Local Agent/Host Ops daemon status and confirm the production Local Agent self revision.
3. Run read-only status for `~/.local/share/local-agent/chat-bridge-cft`.
4. Run Host Ops target inventory against that exact profile endpoint.
5. If exactly one ChatGPT page exists, run read-only readiness using the current Bridge fingerprints and worker diagnostics. Do not reload a healthy page.
6. If `page_count == 0`, perform one controlled `stop -> start` of only `chat-bridge-cft`, with the CfT `current` binary and start URL `https://chatgpt.com/`; then re-run read-only inventory/readiness.
7. Expect five Bridge fingerprints to be `matched`. Worker `running` is nice evidence, but `worker_inactive` alone is not an error because MV3 workers may sleep.
8. `dom_not_ready` on a fresh or logged-out ChatGPT page is not grounds for self-heal. It can simply mean there is no composer such as `#prompt-textarea` yet.
9. Never touch the user's normal daily Chrome profile, never use a broad process kill, and never loop reload/recovery.

If the controlled restart still yields zero page targets, diagnose the managed-session lifecycle rather than changing Bridge fingerprints or recovery logic.

## Useful operator commands

From the installed/current `local-agent` checkout:

```bash
CFT="$HOME/.local/share/local-agent/chrome-for-testing/current/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
PROFILE="$HOME/.local/share/local-agent/chat-bridge-cft"

python scripts/bridge_hostops_session.py status \
  --profile-dir "$PROFILE"

python scripts/bridge_hostops_session.py start \
  --profile-dir "$PROFILE" \
  --browser-executable "$CFT" \
  --url https://chatgpt.com/

python scripts/bridge_hostops_session.py stop \
  --profile-dir "$PROFILE"
```

For a known exact conversation URL, read-only external diagnosis is:

```bash
python scripts/bridge_hostops_recovery.py \
  --profile-dir "$PROFILE" \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID
```

Only add `--recover` after read-only diagnosis reports `content_script_missing` or `content_script_stale` and the exact target/URL guards are satisfied.

## Local Agent / multirepo workflow notes

- `local-agent` itself is intentionally execution-disabled in the multirepo catalog; do not queue ordinary execution tasks against the `local-agent` repository.
- Machine execution for this browser workflow is normally scheduled through the execution-enabled `host-ops` repository using its exact binding.
- The global parallel-supervisor control repository discovered during this work is `growclip`; do not assume `host-ops` owns global daemon control commands.
- Task JSON must include the current schema fields, including explicit `resources` when required by the installed daemon.
- Avoid giant inline task JSON/heredocs; an earlier parser failure was caused by task-file escaping. Prefer small scripts or short deterministic commands.
- Re-check concurrent work before creating branches or scheduling browser resources. Other workflows (notably Kobra/plotter/Fusion) have used the same Local Agent concurrently.

## Related documentation

- `docs/BRIDGE_HOSTOPS_RECOVERY.md` — authoritative recovery contract/runbook.
- `scripts/bridge_hostops_session.py` — dedicated Chat Bridge browser lifecycle wrapper.
- `scripts/bridge_hostops_recovery.py` — exact-target readiness/recovery wrapper.
- Host Ops browser docs: `MichalMatu/host-ops`, `docs/operations/BROWSER.md`.

## Handoff rule

A new planner/session should verify current facts first, then continue from the `Current continuation point` above. Do not reconstruct state from old chat memory when repository/daemon evidence is available.
