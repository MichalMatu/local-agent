# Parent transport arbitration — disabled synthetic preview

Status: **simulation-only / not an execution lock**.

The first private GitHub writer/reader and cold recovery tests prove that a
single synthetic dispatch can be durably recovered. They do **not** yet
prevent a legacy DOM Conversation Fabric driver and a future GitHub-first
driver from attempting the same semantic work.

`github_fabric_parent_fence_preview.py` introduces a strictly bounded
**planning** contract for the future common parent ownership seam. It
projects the exact approved public synthetic operator/child fixture into a
fixed `projects/local-agent/parents/<parent-id>.json` identity derived from
the canonical ChatGPT parent URL and project ID.

Only two transport labels exist: `legacy_dom` and `github_first`.
A parent may have at most one immutable preview record. A byte-identical
same-mode replay has no writes. A competing transport, changed request
digest, missing indexed record, orphaned record, stale origin SHA, forged
ACK, invented browser Send permission, arbitrary private bootstrap or
attempted automatic epoch advancement is rejected.

The preflight returns exactly two prospective Git-tree writes — the immutable
preview and bounded parent index — so a later trusted repository writer can
CAS them in one Git commit. **No writer is included in this PR.** No
corresponding GitHub record is published and there is no live browser
interaction.

All emitted records hard-code:

```json
{
  "kind": "synthetic_parent_transport_arbitration_preview",
  "fence_epoch": 1,
  "phase": "unattested_no_browser_authority",
  "browser_send_authorized": false,
  "ack_state": "not_attested"
}
```

## Requirements before granting any real browser side-effect authority

1. Move the preview to a trusted Local Agent writer with **atomic,
   non-force Git compare-and-swap**, indexed immutable records and
   commit-pinned reads in the private data repository.
2. Define an explicit parent registration and durable mode selection that
   the active legacy DOM driver **and** the future GitHub-first driver
   both check before any child tab creation or Send. A private record by
   itself cannot disable an older extension, offline browser or legacy path.
3. Implement a fenced epoch transition that requires positive, externally
   validated proof of child retirement/terminal status. Timeouts, missing
   ACKs, stale local caches or expiring clocks must never imply safe retry.
4. Bind each semantic-node attempt to the same project/workflow/parent
   authority across browsers and machines. Never confuse an observation
   claim with a permit to execute.
5. Verify genuine browser ACK and trusted terminal result write-back; deny
   replay of potentially submitted prompts with unknown effects.
6. Perform cross-tab, cross-device and restarted/offline worker tests before
   opt-in production enablement.

The preview **does not protect production execution**. GitHub-first remains
disabled; DOM remains the currently active production delivery path.
