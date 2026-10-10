# M8: legacy/offline Chrome exclusion — effect-time safety boundary

Status (2026-10-10): **BLOCKED / SOURCE-ONLY**. This is a threat model and
negative source regression, not an operator acceptance or browser migration
instruction. Do not enable Send, ACK, old-driver retirement or replay.

## What the existing source can do

The production service worker still imports `worker_conversation_fabric.js`
and `worker_spawn.js`. The latter uses `chrome.tabs.create` and
`chrome.tabs.sendMessage` to create/send child bootstrap intent. The
installed content-script graph contains `content.js`, whose composer
submission path can call the live send button's `.click()`. The
`worker_delivery.js` and feedback-claim guard coordinate parent feedback,
but a durable claim or local no-replay marker is not evidence of a server
acknowledgment. These are **current checked-in source capabilities**, not
proof of what is installed on any specific browser/device.

The new GitHub-first public intake remains read-only. The private parent
fence is deliberately not imported by the production worker. A pinned Git
commit, parent index, manifest digest, mode record, CAS or token cannot revoke
a previously installed legacy content script. Its code may operate while
offline or after reconnection without consulting a new GitHub record.

## Impossibility boundary

Consider a legacy extension L that can directly click a ChatGPT composer,
and a future extension N that honors a new GitHub fence. If L is offline
when N observes it as absent, L can reconnect later and click the composer.
The GitHub record is not checked by L and cannot physically prevent that
click. L's silence has the same observable trace as an uninstalled instance.
No protocol between N and GitHub alone can distinguish the cases.

Therefore **global exclusion requires an enforcement point that ALL
potential effect-capable clients cannot bypass**, or independently enforced
retirement/removal of each such client and its authority to operate. A
JavaScript-only epoch/lease in the new extension is not such a point.
Neither a timed grace period nor a negative GitHub read proves retirement.

## Viable decision paths to investigate

1. **Manual-only:** continue using GitHub-first for review, evidence and
   planning, with physical child lifecycle and confirmations performed by
   the operator. It requires no global automated Send/ACK admission.
2. **Controlled fleet retirement:** for a finite, independently enumerated
   collection of browser profiles/devices, remove/disable the old extension,
   invalidate its effect authority, close or reload old script-bearing tabs,
   and verify offline-return and restart behavior. Unknown devices or
   offline installations remain **unverified**, never silently cleared.
   This is viable only if a trusted boundary prevents any unaccounted client
   from accessing the same effect surface, including after reconnection.
   An extension self-report is not sufficient.
3. **Trusted common effect gateway:** use a proven external/browsing-platform
   enforcement mechanism that every relevant client must pass before each
   composer mutation and Send/ACK, including old code. It must deny stale
   epochs without relying on cooperation by L. No such mechanism has been
   established for arbitrary existing ChatGPT DOM extensions in this repo.
   Do not claim that GitHub, a new extension or Local Agent alone provides it.

## Required evidence before any future effect admission

- Enumerate all reachable profile/device/extension/script-bearing session
  classes, including an intentionally disconnected legacy instance; document
  exactly which authority can revoke its ability to cause UI effects.
- Obtain an independently verifiable revocation/host policy proof for each
  class and validate that previously loaded content scripts cannot still
  submit. A missing heartbeat, absent tab, new runtime flag or receipt does
  **not** satisfy this requirement.
- Exercise competing legacy and GitHub-first drivers, simultaneous requests,
  browser reload, suspended service worker, offline return after migration,
  tab restoration, stale claims, ambiguous submit, lost ACK and no-replay.
- Bind the enforced decision to exact parent/workflow/effect identity,
  monotonic epoch, current authenticated session and an atomic effect-time
  admission; stale permissions must never be cached across reconnects.
- Obtain independent security and integration sign-off on the mechanism and
  live browser acceptance for the exact revision. Retain negative test
  outcomes and don't convert a redacted Local Agent receipt into a browser
  execution attestation.

Until all these conditions are met, record **BLOCKED**; do not toggle any
private read/dispatch flags, issue child Send/ACK or claim global old-client
exclusion.

For a privacy-preserving, intentionally unfilled evidence ledger and
operator-approval boundary, see
[LEGACY_BROWSER_RETIREMENT_EVIDENCE_LEDGER.md](LEGACY_BROWSER_RETIREMENT_EVIDENCE_LEDGER.md).
The ledger never issues a production GO or prompts live browser actions.

## Source-only regression (not a retirement certificate)

`local_agent/conversation/github_fabric_browser_source_exclusion.py`
statically enumerates the checked-in service-worker `importScripts` graph
and manifest-injected scripts with bounded inputs. It also requires the
reviewed manifest's exact declared capabilities: permissions, host permissions,
background worker, injected content-script order/matches/world defaults and
absence of unreviewed optional permissions, externally connectable endpoints
or web-accessible resources. Duplicate manifest JSON fields are rejected.
Intentional manifest changes must receive new source review and tests. It fails if the startup
graph becomes dynamic, duplicate or unreviewed, or if a loaded script
references `github_fabric_private_*` or adds another code loader.
The direct service-worker and permitted nested-worker import identities and
ordering are pinned to reviewed lists. A new benign-looking worker script,
reordered bootstrap, or additional nested import also fails the audit until
its effect surface receives deliberate review. The scanner does not prove
that changes *within an already approved script* are behavior-preserving,
that source loaded in Chrome matches the Git checkout, or that old/offline
extensions have been retired. It checks
that the currently observed old DOM effects still exist and that public
GitHub intake remains no-tab/no-Send and default-disabled.

The result **always** sets `browser_effects_permitted=false`,
`old_offline_clients_excluded=false` and
`independent_review_completed=false` even when source inspection passes.
It does not inspect an installed Chrome instance, an offline device or the
ChatGPT application. Future intentional production migration must undergo a
fresh review; it must not treat this source check as authorization.

Focused offline command (source-only):

    python -m unittest -v tests.test_github_fabric_browser_source_exclusion

Related source guard:
`chat_bridge/github_fabric_private_activation_guard.test.js` (still
negative-only). Existing local verification: `LOCAL_VERIFICATION.md`.
