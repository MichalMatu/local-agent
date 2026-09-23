# local-agent v4.11.3

v4.11.3 is a repository-onboarding and topology-documentation patch for the v4.11 bounded-parallel release line.

## Changes

- adds `MichalMatu/esp32_c6_zigbee` as the fourth registered downstream repository, using repository id `esp32-c6-zigbee`;
- records its repository-scoped control/work/checkpoint topology under `~/agent-workspace/repos/esp32-c6-zigbee/`;
- synchronizes the canonical downstream-documentation audit list with the new repository;
- updates the ESP32-C6 Zigbee repository with a root `AGENTS.md` describing Local Agent task/evidence/resource and ESP-IDF hardware rules;
- leaves scheduler behavior, task schema, resource arbitration, watchdogs, execution leases and serial fallback unchanged.

The machine-local registry and new `agent-control` workspace are provisioned and verified separately as a live deployment gate before the release is considered complete.
