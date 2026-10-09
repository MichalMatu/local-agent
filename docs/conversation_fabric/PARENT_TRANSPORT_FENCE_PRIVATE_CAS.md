# Synthetic global parent fence — private atomic CAS writer

Status: **default-disabled source code only; no private fence publication,
no live transport admission and no browser authority**.

This stacked change depends on parent preview PR #209.
It adds github_fabric_parent_fence_private_github.py and expands the trusted
private GitHub REST adapter only for commit-pinned GETs of parents/ records
and bounded recursive Git tree inspection. The REST adapter now enforces
method-specific allowlists: GET only for fixed, commit-pinned synthetic
project/parent paths and exact Git commit/tree SHAs, POST only for immutable Git
object creation and PATCH only for the fixed non-force branch ref update.
Arbitrary project contents and non-SHA refs are rejected before network access.
No Chrome content script receives
a token; there is no production flag, UI Send hook, daemon task, or real ACK.

## Exact opt-in contract

The trusted Python entrypoint requires enabled=True and either an explicitly
supplied private-repository credential or a test-only injected API. It admits
only the exact known-public synthetic fixture; any altered prompt, child
bootstrap or private payload fails before remote I/O. Only the immutable
preview epoch 1 with browser_send_authorized=false and ack_state=not_attested
can be written.

At one immutable Git commit SHA the reader validates:

- exact fabric-data ref and commit tree;
- complete, non-truncated bounded recursive tree enumeration;
- an exact, non-duplicated `parents` root of Git tree type, mode `040000`,
  and literal 40-hex SHA whenever child files exist (missing, malformed,
  symlink-mode or duplicate roots fail closed);
- every parents/ record path, including orphan detection outside the index;
- exact index/record correspondence, canonical global parent identities,
  record integrity and immutable competing transport mode exclusion;
- each present parent index/record Contents response is bound to its exact
  recursive-tree Git blob SHA; both the Contents metadata SHA and Git SHA-1
  calculated over the decoded `blob <length>\\0<bytes>` payload must match.
  The Contents metadata path must also be the exact expected index/record path.
  Missing tree entries, Contents 404 for an advertised blob, wrong paths or
  mismatched bytes fail closed before any write.

The writer creates exactly two Git blobs and one tree with the parent
record and bounded global parents/index.json; one commit with pinned parent
and one non-force ref update. It accepts no partially published record/index
state. Byte-identical restart/replay writes nothing. A ref race or lost
update acknowledgment triggers a fresh complete snapshot; a conflicting
mode cannot acquire ownership. Invalid remote state fails closed.

Git ref fast-forward-only arbitration is not an application-level conditional
request header. Divergent commits built from the same parent cannot both
become head; reread the resulting head before reporting convergence.

## Verification limits

Deterministic tests cover atomic two-path write, replay, ref conflicts, lost
acknowledgment, orphan/dangling index, malformed tree, mismatched blob metadata,
semantically valid but stale Contents bytes, altered decoded bytes with forged
metadata, wrong Contents paths, missing advertised blobs and forged Send/ACK.
Mac/sandbox unit tests and local fakes are not a real private GitHub write, browser ACK,
old DOM driver quiescence or cross-device execution evidence.

Before production activation, both transports and already-open or older
browser workers must honor one authoritative parent mode/epoch before tab
creation, composer mutation or Send. Unknown submission or worker absence
never grants takeover. Child acknowledgment, terminal results and explicit
retirement require separate evidence.
