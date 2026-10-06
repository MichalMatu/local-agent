# Sequential delegation hardening baseline — 2026-10-06

This checkpoint freezes the clean source baseline before any new sequential delegation-cycle implementation work.

## Source rollback anchor

```text
repository: MichalMatu/local-agent
branch: main
runtime/source anchor: 59c5d699bc32283ebb98fc026f76128ec9db6d2a
Local Agent release line: 4.20.6
Chat Bridge source manifest: 0.8.4
```

The runtime/source anchor above contains the final pre-checkpoint behavior changes. GitHub Actions run #2259 completed successfully on that exact main commit with all five jobs green:

- `test`;
- `coverage`;
- `python-314`;
- `macos-smoke`;
- `bridge-browser`.

The final roadmap refocus commit `bf854147624c5e90dd3b61bbe9ff3577c55ee45d` also passed main CI #2255 with all five jobs green.

## Final pre-checkpoint repair

PR #171, **Align Fabric feedback with current ChatGPT submit path**, was merged as `59c5d699bc32283ebb98fc026f76128ec9db6d2a`.

The field symptom was concrete: Conversation Fabric feedback could be inserted into the ChatGPT composer without a successful submit, then retries could repeat the insertion/spam behavior.

The repair:

- recognizes the current `data-testid="composer-submit-button"` variant while retaining the older selector;
- uses the same bounded live-button re-resolution and submit fallback pattern as normal Bridge delivery;
- adds DOM regression coverage that no longer depends on the legacy `#composer-submit-button` id;
- keeps exact prompt reconciliation/no-replay protections from the preceding terminal-feedback fix.

PR #171 exact-head CI #2258 was 5/5 green and post-merge main CI #2259 was 5/5 green.

## Live Bridge state

The live normal-Chrome Bridge is deliberately **disabled** after the observed submit/retry spam incident.

The fixed source at `59c5d699...` has not been reloaded or live-accepted after that incident. Do not infer a successful deployed fix from the source CI. Re-enabling/reloading is a separate explicit operator validation step.

The optional `operator_status_url` activation is also unverified.

## Product direction frozen here

The former bounded multi-goal supervision plan is retired.

The final product stage is **sequential delegation-cycle hardening**:

1. one parent conversation owns exactly one project/main goal;
2. for task A it may delegate 1–4 reasoning-only children;
3. results are durably captured, missing coverage is explicit, the parent synthesizes, and only exact owned child tabs are closed;
4. campaign A must be terminally settled before task B starts;
5. task B uses a fresh campaign with no ownership/result/terminal-delivery leakage from task A;
6. repeated cycles must survive restart, timeout and manual/retained-composer recovery without replay, duplicate child creation or zombie tabs;
7. automatic child replacement/redelegation and multi-goal parent supervision remain non-goals;
8. repository/machine execution authority remains exclusively with the parent plus canonical target admission.

## Branch hygiene

A fail-closed one-shot cleanup ran successfully after verifying exact branch heads and zero open pull requests.

The repository branch set is now exactly:

- `main`;
- `chat-bridge-state` — protected operational runtime-state branch;
- `operator-control` — protected operational control branch.

All 14 short-lived development/test/docs branches present during this closeout were removed. The one-shot cleanup workflow was then removed from `main`.

## Next action

Do not start broad new functionality from this checkpoint.

The next code work is the bounded final hardening stage above, beginning with production-shaped regressions for two successive campaigns in one parent and the observed delayed/failed automatic submit path. Keep the live Bridge disabled until a deliberate post-fix acceptance step is chosen.
