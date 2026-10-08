# Synthetic semantic claim admission preview

Status: **default-disabled, synthetic-only, no execution authority**.

The new `github_fabric_claims.py` and `github_fabric_claims_github.py`
exercise the smallest atomic GitHub admission transaction without enabling
GitHub-first child spawning, private bootstrap publication or a second browser
scheduler. Source files remain in the public code repository, and the
`chat-bridge-state` target is **public**.

## Identity and atomicity

A claim ID is derived only from `(workflow_id, workflow_node_id)`, using a
domain-separated SHA-256 input. It therefore does **not** inherit the
incompatible DOM and GitHub campaign/transaction hash algorithms.
The immutable claim also records the admitted child request digest, dispatch,
parent and spawn transaction, and has the explicit
`mode=synthetic_observation_only` and `phase=admission_preview`.
It must **never** be interpreted as permission to create a tab or click Send.

The trusted writer constructs a single Git tree containing every missing
semantic-node record **and its updated bounded index**. It then fast-forward
updates `chat-bridge-state` exactly once. A reader can see either all
records and the discoverable index or neither. The writer uses commit-pinned
reads, denies orphaned records and dangling index references, rejects
same-semantic-node/different-content conflicts, and re-reads origin after
lost acknowledgements or a racing writer. Nothing is force pushed.

All mutation is behind a default-disabled explicit opt-in and the exact
pre-existing known-public synthetic fixture fingerprint. Chrome has no
writer, token, new poller, or imported claim model. No real content is
published, even if a caller labels an object `synthetic`.

## Gates before production activation

1. A single authoritative **parent transport mode** and fencing epoch must
   exclude old DOM dispatches while the new GitHub owner is active. Existing
   legacy submitted or ambiguous work must be reconciled; a missing receipt
   is not proof that no Send occurred. Old extension installations not
   enforcing the freeze cannot join the ownership transfer.
2. Real private bootstrap and evidence require a separately authorized
   private repository or encrypted transport. A branch inside this public
   repository is not private, nor does a digest encrypt content.
3. A browser runner must prove durable original-tab ownership and carry a
   fenced semantic claim before touching the composer. `sessionStorage`
   alone is not cross-tab or cross-device authority.
4. A trusted ACK/result route and verified terminal evidence must be
   recorded and reread from GitHub for multi-device recovery. The
   `bridgeGithubFabricReadOnlySeen` ledger proves observation only.
5. All negative, replay, restart, double-Send and credential-leakage tests,
   plus normal Chrome acceptance, must pass before any production flag flip.

This preview is not a live GitHub-first implementation. It is safe to merge
without changing the existing browser route, but **not** safe to use as
an execution admission token or to publish private child text.
