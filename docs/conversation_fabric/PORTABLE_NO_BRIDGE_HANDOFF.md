# Portable no-Bridge manual new-parent handoff (draft)

This draft stacks on PR #243 (synthetic, read-only GitHub cold recovery).
The new portable manifest is **manual data for operator review**, not a
migration activation token and not an executable command.

## Flow

1. The operator creates a *separate* destination parent conversation and
   independently pins the origin's GitHub source commit SHA.
2. The known-public synthetic recovery reader (public or private GitHub) runs
   with enabled=True, GET-only remote operations, strict fixture preflight,
   and an exact source commit comparison via PR #243's
   preview_manual_new_parent_from_github().
3. export_manual_handoff(preview) generates at most 4096 bytes of canonical
   JSON, containing only the source/destination URLs, source SHA, source kind,
   synthetic workflow/dispatch/child IDs, schema, immutable deny-only flags,
   and manifest_digest.
4. The user may carry this data to a new ChatGPT conversation *manually*.
   import_manual_handoff(...) checks exact canonical JSON, duplicates,
   integrity, independently pinned SHA, expected destination, and deny-only
   permissions, and returns a frozen read-only preview. No ChatGPT connection
   or browser side effect occurs.
5. Before relying on the carried metadata,
   verify_manual_handoff_against_github(..., enabled=True) re-reads the
   approved synthetic source using the existing GET-only recovery and demands
   an exact match with the imported preview. Failure does not retry a Send,
   create a task, or repair source records automatically.

## Security invariants

- Every remote-verification entrypoint is **default disabled**.
- Origin SHA agreement is only a consistency check: the *operator* must
  establish independent GitHub provenance; the provided API itself is not
  authenticated here. Never treat a caller-chosen 40-character SHA as trust.
- The included manifest_digest is SHA-256 over deterministic payload JSON.
  It detects accidental corruption, **not deliberate substitution**; anyone
  can recompute it. The independently pinned, GET-only source recheck is
  necessary to detect modified workflow identities or forged data.
- An imported manifest cannot authorize execution, retry, ACK, terminal
  result, browser effects, or retirement of offline/uncooperative extensions.
- There are no private prompts, bootstrap content, tokens, request digests,
  terminal receipts, child conversation URLs, or browser session handles
  in the exported JSON.
- The destination must remain outside the old legacy browser automation.
  A new URL does not globally fence legacy workers, even after a successful
  source recheck. Do not migrate real/private user requests or trigger a
  ChatGPT send based on this synthetic preview.
- No cloud Actions, Chat Bridge, Codex, daemon restart, agent execution
  policy/config changes or production browser automation are included.

## Verification

New tests exercise round-trip public/private JSON, deterministic encoding,
digest/identity/authority rejection, malicious recomputed digests, unknown
fields, duplicate JSON keys, size ceilings, source/destination mismatch,
no-remote-I/O invalid input, and GET-only recovery with the repository's
actual in-memory GitHub reader fixtures. Exact-head Mac test evidence and
independent security review remain separate acceptance gates.

PR #243 remains draft and must be reviewed before this stacked draft can merge.
