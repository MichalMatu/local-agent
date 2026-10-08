# Private Fabric project-scoped synthetic publication

Status: **default-disabled / known-public synthetic fixture only**.

The trusted Local Agent now has a private GitHub writer skeleton for
`MichalMatu/local-agent-fabric-private`, branch `fabric-data`.
It is restricted to the exact previously public synthetic operator fixture
and `project_id=local-agent`, `workflow_id=workflow-001`.

The writer is separate from the public GitHub control branch writer.
It authenticates to a hard-coded private GitHub REST repository and refuses
redirects. Its explicit credential is never stored in Chrome, the page DOM,
the public runtime JSON, or test output. No local credential is acquired
implicitly and production enablement is unchanged.

Its publication order is:

1. Verify the exact synthetic fixture fingerprint before any network I/O.
2. Resolve current `fabric-data` origin and pin all reads to the same SHA.
3. Verify `projects/index.json` includes `local-agent` and
   `projects/local-agent/workflows/index.json` is well formed.
4. Write the immutable dispatch record under
   `projects/local-agent/workflows/workflow-001/dispatches/<id>.json`.
5. Update the dispatch index **only after** the record is verifiable.
6. Update the project workflow index **last** so a cross-device reader
   cannot discover incomplete workflow records.
7. After uncertain GitHub writes, 409 or 422 conflicts, reconstruct from the
   fresh Git origin. Identical replay requires zero new writes.

The three stages are compare-and-swap fast-forward-only commits.
All source, indexes and records are size/identity validated. No child is
spawned, no Send is triggered, and this test does not prove consumer ACK
or terminal result evidence. No real private prompt is yet admitted.

Future live enablement still requires parent-mode exclusion from legacy DOM,
trusted actual private request admission, protected browser read credential
lifecycle, genuine child ACK, verified terminal result and recovery tests.
Do not relax the fixed fixture allowlist without those gates.
