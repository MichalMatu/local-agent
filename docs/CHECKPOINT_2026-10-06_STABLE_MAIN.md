# Stable main checkpoint — 2026-10-06

This checkpoint records the known-good `main` state before further correctness work. It does not merge new runtime behavior.

## Rollback anchor

```text
repository: MichalMatu/local-agent
branch: main
commit: 2d99fad80ab6e455301354dc53ee894a852b0bd6
tree: 8a3a270dbaf5bad35bf2b1ec5538c9cdf2b9ff1a
Local Agent release line: 4.20.6
Chat Bridge source: 0.8.3
```

The commit SHA above is the source rollback anchor. To inspect or recover it without rewriting an existing branch:

```sh
git fetch origin
git switch -c recovery/stable-main-20261006 2d99fad80ab6e455301354dc53ee894a852b0bd6
```

## Why this state is frozen

Operator acceptance has confirmed the currently deployed Conversation Fabric path can delegate child chats and close owned child tabs after result capture. This checkpoint preserves that working baseline before the two still-open follow-up PRs are considered.

The current `main` tree at the rollback anchor is byte-for-byte the same Git tree as the tested head of PR #155 (`e6334b8adc5848919ae3995c70c08a4dae1e6616`). GitHub Actions run `37219374334` completed successfully on that exact tree with all five jobs green:

- `test` — compile, lint, Chat Bridge validation, unit and integration tests;
- `coverage`;
- `python-314`;
- `macos-smoke` — process, checkpoint, multi-repository, binding, emergency-control and MCP smoke coverage;
- `bridge-browser` — real extension delivery and restart smoke.

No runtime source change is part of this checkpoint documentation or its branch-hygiene cleanup.

## Included state

The frozen baseline includes the already-merged Conversation Fabric and runtime hardening through `main@2d99fad80ab6e455301354dc53ee894a852b0bd6`, including:

- browser-native child delegation in the existing authenticated Chrome session;
- durable child campaign/result recovery and exact owned-tab cleanup;
- terminal feedback replay protections and durable at-most-once delivery guard;
- canonical runtime-catalog / binding admission checks;
- fail-closed daemon-registry startup behavior;
- crash-safe dedupe completion recovery;
- serial/parallel worker admission parity;
- current architecture and operations documentation.

## Intentionally not included

Two short-lived branches remain active and are not part of the rollback anchor:

- `fix/idle-output-activity-20261004` — open PR #157;
- `test/fabric-restart-e2e-20261004` — open PR #158.

They must be reviewed and merged or closed independently. The checkpoint must not be advanced merely because either branch exists.

## Branch hygiene at checkpoint

Permanent branches:

- `main`;
- `chat-bridge-state`;
- `operator-control`.

Active short-lived branches retained intentionally:

- `fix/idle-output-activity-20261004` (#157);
- `test/fabric-restart-e2e-20261004` (#158).

Historical branch cleanup was completed on 2026-10-06 after this checkpoint was recorded. The following merged branches were removed:

- `docs/current-architecture-20261004` — PR #155;
- `fix/cf-terminal-at-most-once-p0-20261004` — PR #147;
- `fix/cf-terminal-delivery-replay-p0-20261004` — PR #145;
- `fix/cf-terminal-history-replay-p0-20261004` — PR #146;
- `fix/conversation-fabric-partial-failure` — PR #142;
- `fix/dedupe-crash-recovery-20261004` — PR #153;
- `fix/legacy-agentd-admission-20261004` — PR #154;
- `fix/preflight-repository-id-casefold-20261004` — PR #150;
- `fix/runtime-admission-hardening-20261004` — PR #148;
- `fix/runtime-low-cleanup-20261004` — PR #149;
- `fix/serial-parallel-admission-parity-20261004` — PR #156;
- `work/cf-ordering-retry-20261004` — PR #152;
- `work/fix-cf-lifecycle-recovery-20261004` — PR #144;
- `work/fix-cf-terminal-and-dedupe-retry-20261004` — PR #143;
- `work/runtime-audit-repair-20261004` — PR #151.

The temporary checkpoint/cleanup branches used to record and perform this cleanup were also removed. The post-cleanup branch set is therefore exactly the three permanent branches plus the two intentionally active PR branches listed above.

Do not delete the permanent state/control branches or either currently open PR branch as part of historical cleanup.

## Checkpoint discipline

Future work should branch from current `main` and remain small and independently verified. If later changes regress delegation, terminal delivery, child cleanup or runtime admission, compare against this recorded anchor first rather than weakening the current safety checks.
