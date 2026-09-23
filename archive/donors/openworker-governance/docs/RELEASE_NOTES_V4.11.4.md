# local-agent v4.11.4

v4.11.4 is a documentation-alignment patch for the v4.11 bounded-parallel release line.

## Changes

- updates the canonical `docs/OPERATIONS.md` downstream documentation gate to include all four registered repositories, including `MichalMatu/esp32_c6_zigbee` (`esp32-c6-zigbee`);
- records the Growbox documentation audit: `main` and `mvp/environment-controller` no longer require supervisor-only `max_parallel_workers` in every repository-worker status snapshot;
- removes stale v4.10/global-serial assumptions from the Stage27C continuation documents and describes bounded-parallel execution with conservative machine exclusivity for hardware/serial/soak tasks;
- leaves scheduler behavior, task schema, resource arbitration, watchdogs, execution leases, control semantics and serial fallback unchanged.

This release is docs/version-only. Exact-SHA CI and live self-update verification are still required before tagging.
