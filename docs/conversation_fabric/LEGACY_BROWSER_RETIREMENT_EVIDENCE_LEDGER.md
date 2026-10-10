# M8 legacy/offline browser retirement evidence ledger

Status: **EMPTY TEMPLATE / NO GO / NO BROWSER AUTHORITY**.

This is a review-only checklist for Milestone 8 GitHub-first Conversation
Fabric. It does not install, launch, interrogate, disable, terminate, reload,
uninstall or submit through Chrome. It does not start GitHub-first Send/ACK.
Do not complete this template using inferred, invented or stale facts.

Do not commit a *filled-in* ledger, device identifiers, browser profile paths,
tab URLs, extension storage, credentials, personal account details or policy
exports to GitHub. Keep the source of sensitive evidence under operator
control. PR comments and Local Agent task results should include only
redacted aggregate statuses and opaque proof references.

## Threat model and exact decision being tested

A legacy Chrome extension may already have placed a content script in a
ChatGPT page; the script may have direct composer/Send access without
consulting a GitHub record or new epoch fence. It may continue on an open
page after its extension is removed, and an old offline machine may return.
The GitHub-first implementation has no common trusted effect-time gate that
those uncooperative old scripts must obey.

The question is **not** "is the latest extension's source safe?" It is:
"Can *any* earlier effect-capable browser process or already-loaded script
still submit to the same ChatGPT parent after the migration?" Absence of a
GitHub heartbeat, presence of a new extension, a locally empty process list,
or an uninstall report on one Mac cannot establish the global negative.

No set of *self-reported* entries below is independently sufficient to
authorize Send/ACK. The decision remains **NO GO** until an independently
reviewed, externally enforceable exclusion mechanism and browser acceptance
are demonstrated for the complete deployment scope.

## Allowed evidence collection phases

### Phase 0 — source-only (permitted without live browser inspection)

- Pin the repository and exact GitHub commit for the existing browser
  driver and source guard, including `service_worker.js`,
  `worker_spawn.js`, `content.js` and `manifest.json`.
- Read the source-only negative scanner results and the local tests'
  exact-head receipts, recording truncation and failed historical tests
  without relabeling them.
- Identify what existing Host Ops commands could later assist read-only
  inspection: `browser inspect`, `browser-session status`, and CDP
  attach inspection. Do not call them on live profiles yet.
- Document known coverage limits: `browser-session status` covers only
  an exact Host Ops-managed profile; it does not enumerate every Chrome
  profile or disconnected host. CDP inspection can expose URLs, titles and
  session data; it also does not prove extension revocation.

### Phase 1 — operator-approved, strictly scoped passive inspection

Requires separate explicit authorization identifying the host(s), Chrome
profiles or managed sessions and the data classes that may be observed.
Only execute individually reviewed read-only commands after that approval.
Do not collect raw tab titles/URLs, cookies, local storage, extension state
payloads or login identifiers unless expressly authorized and necessary.

For each inspected host, distinguish at least:

1. Browser processes currently visible.
2. Known user/profile installations and extension identity/version.
3. Managed vs unmanaged Chrome policy and policy application evidence.
4. Tabs that may already contain injected legacy scripts, including
   suspended and session-restore tabs.
5. Devices offline or absent from the inspection and whether the fleet
   scope is independently known to be closed.
6. Whether the evidence comes from OS/host policy, a browser process,
   the extension itself or a human declaration.

The host that performed the inspection is **not** automatically a trusted
revocation authority for every offline or unmanaged device.

### Phase 2 — separately approved, potentially destructive tests

Do not perform as part of passive inspection. Each requires specific
approval and a rollback/recovery plan: changing managed policies, disabling
or uninstalling extensions, killing browser processes, reloading/closing
tabs, clearing session restore, logging out, changing credentials, or
actually attempting a ChatGPT submission. A live Send test also requires
its own safety limits, isolated test parent, no-replay policy, and consent.

## Redacted evidence record schema (manual)

Create one private record per **known endpoint class**, not necessarily
one row per individual host. Use local opaque aliases only; no URLs, hostnames,
real profile paths or tokens.

| Field | Accepted values or meaning |
| --- | --- |
| `scope_alias` | Opaque short local alias, e.g. `fleet-class-01` |
| `endpoint_class` | `managed_online`, `unmanaged_online`, `offline_known`, `unknown` |
| `scope_enumeration` | `externally_closed`, `partial`, `unknown` |
| `extension_state` | `installed`, `disabled`, `removed`, `unknown` |
| `existing_page_scripts` | `could_remain`, `externally_excluded`, `unknown` |
| `enforcement_authority` | `trusted_host_policy`, `host_control`, `client_self_report`, `none` |
| `effect_time_exclusion` | `independently_proven`, `not_proven`, `unknown` |
| `offline_return_test` | `independent_negative_observation`, `not_tested`, `not_applicable` |
| `proof_reference` | Private opaque reference and timestamp, not raw evidence |
| `independent_reviewer` | `not_assigned` or separate authorized review record |

No `independently_proven` value is acceptable merely because a human or
extension declared removal, because GitHub has an immutable pinned receipt,
or because the *new* extension honors a fence. A credible assertion requires
a trusted mechanism that can prevent effects from the *old* code without
that old code's cooperation, together with tested coverage and provenance.

## Required adversarial coverage

| Scenario | Acceptable evidence | Missing evidence means |
| --- | --- | --- |
| Old installed client active while new client attempts same parent | Independently observed denial at the common effect boundary, *before* composer/Send | **NO GO** |
| Old client disconnected before migration and returns later | Controlled offline-return negative test with enforced revocation that survives reconnection | **NO GO** |
| Extension removed while legacy script remains in loaded ChatGPT page | Previously loaded page can no longer submit, confirmed by a trusted host/browser boundary, not extension self-report | **NO GO** |
| Browser restored from previous session | Restored tabs and worker lifecycle are examined under enforced denial | **NO GO** |
| Worker suspended/restarted or parent epoch changed | Every stale action must reacquire trusted effect-time admission; no cached permission | **NO GO** |
| Lost ACK or ambiguous Send | No automatic replay; outcome remains unknown for manual resolution | **NO GO** |
| Unmanaged/unknown device or Chrome profile | Explicitly removed from the deployment scope by independent authority, or universally bound by an enforceable effect gateway | **NO GO** |
| Test and review provenance | Exact revision, complete source and execution evidence, independent security/integration review, negative tests retained | **NO GO** |

## Gate verdict

**Current verdict: NO GO — legacy/offline Chrome exclusion unproven.**

The only permissible automatic output of this ledger is a list of
**missing evidence**. Do not compute `browser_effects_permitted=true`,
`ack_authorized=true`, `old_clients_excluded=true`, or a positive
production migration verdict from the ledger.

If even one effect-capable endpoint class remains outside the trusted
enforcement scope, no globally safe automated Send/ACK takeover exists in
the documented architecture. Continue manual parent/child lifecycle with
GitHub-first read-only evidence. Seek independent review before any change
to the production browser authority model.

## Sources and nearby artifacts

- `LEGACY_OFFLINE_BROWSER_EXCLUSION_GATE.md` — architectural blocker
  and bounded source scanner.
- `M8_NO_BRIDGE_SECURITY_CHECKPOINT_20261010.md` — historical PR and
  Mac receipt pins; follow-up draft #267 and #268 add import-identity
  guarding and fixture-only lease descriptor isolation.
- Chromium extension security FAQ (previously injected content scripts):
  https://chromium.googlesource.com/chromium/src/+/main/extensions/docs/security_faq.md
- Chrome Enterprise extension management:
  https://support.google.com/chrome/a/answer/9867568?hl=en-1

A browser task must never be published merely by populating this template.
