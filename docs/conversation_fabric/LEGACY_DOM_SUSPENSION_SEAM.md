# Legacy DOM browser-effect suspension seam (source-only draft)

Status: **unmerged, local fail-closed deny latch; NOT global transport admission**.

This change installs a minimal check before cooperating-worker Chrome
child-tab creation/reattachment, content preparation, legacy spawn
navigation/probing/injection, child result observation, owned-tab cleanup,
and parent terminal/regular feedback DOM submission. It does not import the private GitHub parent reader, does not access
credentials, does not create any GitHub-first browser action and does not
produce or authorize a parent-mode record.

The existing Chrome storage key
`conversationFabricLegacyDomEffectSuspension` is deliberately **absent** on
older/current installations. In that default state, legacy DOM delegation
continues unchanged. If any value is present, even `false` or `null`, new
child browser effects are denied. Storage read errors and malformed responses
also deny. There is no production writer or automatic setter for the key in
this PR. A future explicit, authenticated migration would need a durable
source-of-truth transition and positive acknowledgment before setting such a
local suspension marker.

## Critical limitations

- An already-installed or offline Bridge version that lacks this code **cannot
  be stopped by the local marker**. A missing marker is not proof that any
  other driver has retired. This is one upgraded-driver seam, not a globally
  authoritative fence and not a permission for GitHub-first.
- The check is asynchronous and not atomic with the Chrome tab/Send effect.
  A marker written between the check and Chrome's effect is not retroactively
  protective. Later stages require trusted epoch-bound reservation and actual
  effect-claim receipt or equivalent browser authority, plus tests for racing
  writers.
- This revision now guards known worker-side parent feedback, child result
  and owned cleanup effect sites when the marker is present. It does **not**
  fence already queued content-script DOM clicks, scripts already running,
  direct user interactions, unknown/new browser sites, or old extension
  builds. Complete content-side and race auditing remains necessary before
  any live mode migration.
- The private `parents/` namespace remains absent. GitHub-first Send/ACK
  remains disabled. There is no rollback/retirement authorization in this
  draft, and clearing local storage is **not** a globally valid rollback.
- The PR must not be merged or shipped without independent safety/integration
  review, exact-head Node/Chromium tests and live explicit operator acceptance.

## Regression evidence to collect

1. The pure Node negative suite checks absent-key legacy compatibility, all
   present-key states, malformed storage and thrown reads.
2. A static side-effect map asserts the two Chrome child-tab creation sites,
   existing bootstrap/inspect messages, additional probe/navigation/injection,
   child result/cleanup, and worker-side parent feedback read the marker.
   These source counts are not effect-time atomic and cannot prove external
   exclusion.
3. Full Bridge Node tests and isolated macOS Chromium/MV3 delegation smoke on
   the same commit prove that a default-absent marker does not break existing
   DOM behavior.
4. A future gated browser test must inject a present marker *during* an active
   campaign and prove no later creation/Send effects, while retaining ambiguous
   earlier effects as unresolved, not replaying them.

This is groundwork for **shared parent-scoped mode arbitration**. It is
insufficient on its own to enable or merge #209/#214.
