# Local Agent 4.18.2: remove standalone C6 execution

At the operator's explicit request, remove `esp32-c6-zigbee` from the canonical agent catalog, live registry and Chat Bridge runtime. Remove its local control/work/checkpoint workspace and repository runtime metadata after quiescent lease checks. Preserve historical checkpoints and non-cache recovery inputs in an archive outside the active workspace before cleanup.

The active executable repositories are LiteGraph, Growbox ML Controller, MatrixHub and Tracker. C6 development continues inside LiteGraph. Existing C6-bound conversations fail closed with `binding_catalog_mismatch`; the Bridge never rebinds them automatically.

This release includes all [4.18.1 Bridge corrections and planner workflow updates](RELEASE_NOTES_V4.18.1.md). Chat Bridge remains version 0.5.0. No Python execution semantics change beyond the release version and deployed registry configuration.

Downstream audit: the ten-document synchronization recorded for 4.18.1 remains current. The archival C6 `AGENTS.md` additionally records removal from the registry/catalog and the explicit Rebind boundary. Other downstream task, resource and control contracts are unchanged by this retirement.

Validation uses `python scripts/verify.py`, the macOS smoke profile and the isolated Chromium profile on the exact release candidate. Live evidence records the active repository probes, cancellation/global-disable checks, recovered enabled state and cleanup paths. Current live ChatGPT DOM and operator extension reload remain separate from the offline Chromium tests.
