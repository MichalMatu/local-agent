# Manual new-parent rehydration — source-only review preview

This is a **separate-parent, no-Bridge** planning seam. It does not install,
configure, restart, or use the Chat Bridge, send a ChatGPT prompt, perform a
GitHub mutation, publish a Local Agent task, claim a child, or retire old DOM
workers. It is deliberately independent of the unmerged #209/#214/#239/#241
branches and changes no running service.

The Python function `github_fabric_manual_new_parent.preview_manual_new_parent()`
accepts only redacted dictionaries from `dataclasses.asdict()` of the existing
**public or private synthetic cold-recovery DTOs**. The operator must first
perform the existing independently verified, commit-pinned GitHub recovery
read and supply that SHA separately. The function checks strict
identity/shape, exact SHA agreement, both canonical URLs, a **different**
destination parent, and the two unconfirmed synthetic child identities.
It rejects new/private prompt fields, forged terminal/ACK status, missing,
duplicate or malformed children. It returns just non-secret identifiers
and a frozen, **read-only review** result.

The SHA comparison is only consistency validation: this function does
**not** authenticate GitHub provenance or know whether the supplied DTO is
genuine. A new parent URL does **not** imply that an old or offline legacy
extension cannot be manually or automatically bound to that URL. The
operator must ensure the destination remains outside legacy automation and
manually review any data before adding it to the destination. Old child
Send/effect/ACK state must never be copied forward as authorization or
silently retried.

Returned fields always include:
- `decision="manual_read_only_review"`
- `browser_effects_permitted=False`
- `automatic_retry_permitted=False`
- `legacy_worker_retirement_proven=False`

This is **not** live arbitrary/private conversation migration. No migration
switch, browser Send, cross-device effect fence, live rebind, or private
execution is enabled. Do not merge without independent review and exact-head
Mac/local regression evidence. Existing legacy DOM functionality is unchanged.
