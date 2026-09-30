# Local Agent 4.19.10

## Summary

Local Agent 4.19.10 freezes the post-4.19.9 Chat Bridge control-plane hardening as Chat Bridge 0.6.1.

The runtime behavior was implemented and reviewed after 4.19.9, then production-shaped field validation was repeated after the normal/daily Chrome profile was explicitly reloaded from the merged `main` checkout. The release does not add another scheduler, another transport or a speculative submit retry. It packages the already-validated hardening under an unambiguous patch version.

## Chat Bridge 0.6.1 hardening

The GitHub-backed managed-conversation control plane remains authoritative for `STATUS`, `PAUSE`, `RESUME`, `NEXT` and `INTERVAL`. Chat Bridge 0.6.1 retains runtime schema 3, content protocol v13 and assistant guard v8 while hardening the service-worker ownership boundary:

- serialize full GitHub desired-state reconciliation inside one MV3 worker instance;
- bypass ordinary runtime cache and older in-flight reads at control boundaries;
- prevent a cold/fresh profile from replaying an already-expired one-shot `NEXT`;
- make each applied `control_generation` payload immutable through a canonical signature and reject rollback/same-generation rewrites;
- keep GitHub ownership sticky across network failure, malformed publication, temporarily missing control records, rollback and generation conflict;
- clear applied ownership only on explicit Remove/new binding lifecycle;
- serialize Remove/Rebind against reconciliation so a removed conversation cannot be resurrected by a concurrent reconcile;
- reject local per-chat pacing mutations while GitHub owns that binding revision;
- render managed per-chat enable/interval state read-only with the visible `GitHub managed` ownership badge;
- keep the global Bridge Master switch local/operator-owned;
- retain assistant LAB schedule/status controls only as managed-chat compatibility no-ops.

No shared cross-profile lease is introduced. The supported deployment remains one normal/daily Chrome-profile executor per managed conversation; the second Chrome profile is diagnostic only and must not concurrently execute the same managed conversation outside an intentional bounded test.

## Wake submission boundary

The composer/Send path is intentionally unchanged by this patch. Delivery still requires the exact conversation, no active Stop state, Bridge-owned composer content, worker authorization, live Send re-resolution and exact submitted-user confirmation. No blind second click or automatic resubmit was added because the earlier field anomaly did not establish a safe duplicate-free retry condition.

## Exact production-shaped field proof

The hardening-specific field gate was completed on 2026-09-30 against conversation `chat-be9defd7`, bound to `MichalMatu/local-agent` at binding revision 1:

1. the normal/daily Chrome checkout was confirmed on merged `main` revision `39aecf90efef1ef03b5facdab837ba8366eaeb85`;
2. the unpacked Chat Bridge extension was manually reloaded from that exact checkout;
3. generation 4 armed one exact `NEXT` for `2026-09-30T15:09:00+02:00`;
4. without `Run now` or assistant LAB scheduling, the automatic wake arrived at approximately `15:09:15+02:00` with the exact immutable `chat-be9defd7` / `local-agent` envelope;
5. generation 5 immediately returned the desired state to `PAUSED`, `enabled=false`, `next_wake_at=null`;
6. the post-run popup visibly showed `GitHub managed`, `github_control_paused`, `Paused`, the `GitHub interval` label and disabled per-chat schedule controls.

The later documentation-only closure was merged at `a78327a30f3e1ac7c1465e4413f77b6cd8a86046`. The 0.6.1 manifest/version bump is release metadata over the same validated hardening behavior; it does not change the service-worker scheduling or delivery logic proven above.

## Verification history

Before this release metadata freeze:

- the hardening implementation candidate passed the complete five-job CI matrix;
- the documentation-cleanup/final hardening heads passed the same complete matrix;
- final field-proof documentation PR #120 passed `local-agent CI` run 1472 / `36720710199`, including `test`, `coverage`, `python-314`, `bridge-browser` and `macos-smoke`;
- the live desired state ended PAUSED at generation 5.

The exact 4.19.10 release candidate must again pass the complete five-job matrix after the version, manifest, release notes and changelog metadata are applied.

## Downstream documentation audit

The shared task/executor contract is unchanged: task schema, bindings, planner scope, resources, concurrency, status/result fields, launchd deployment and self-update semantics are unchanged.

The registered downstream documentation was re-audited for the Chat Bridge scheduling contract:

- `growclip` already documents Chat Bridge `0.6.0+` managed conversations as GitHub-backed and explicitly forbids assistant LAB schedule/status pacing;
- `bloomml`, `MatrixHub` and `tracker` contain no competing Chat Bridge schedule transport text requiring synchronization for this patch.

No downstream source/document edit is required for 4.19.10.

## Versions

```text
Local Agent:      4.19.10
Chat Bridge:      0.6.1
content protocol: 13
assistant guard:  8
runtime schema:    3 + optional conversation_controls
```

## Rollback

The immediate source rollback point is `v4.19.9`. Before rolling back the extension, keep every managed conversation desired record PAUSED (`enabled=false`, `next_wake_at=null`) so an older scheduler cannot emit a surprise wake.
