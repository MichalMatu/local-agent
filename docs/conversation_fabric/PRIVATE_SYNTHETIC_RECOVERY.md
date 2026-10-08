# Read-only private Fabric synthetic cold recovery

Status: **default disabled, synthetic-only, does not grant execution**.

The private data plane at `MichalMatu/local-agent-fabric-private` now has
project-scoped empty catalogs, and the trusted Local Agent publisher can
populate one known-public synthetic fixture under:

```text
projects/local-agent/workflows/workflow-001/dispatches/
```

`github_fabric_private_recovery.py` provides a separate **read-only** way
to verify a fully discoverable synthetic dispatch from one immutable GitHub
commit. It verifies the exact public test-fixture digest before any remote I/O,
pins the private branch SHA, validates the project and workflow catalog and
immutable dispatch, and returns only bounded child identity/digests, never
bootstrap text or browser credentials.

An indexed but missing record, partial workflow catalog, mutated dispatch,
permission denial or malformed origin fails closed. Repeated reconstruction
cannot write to GitHub or trigger Send. The returned state always says
`published_execution_unconfirmed`. A real browser ACK and authoritative
terminal result still require dedicated verified evidence.

The published source remains restricted to the synthetic fixture. Real
private user text must not be enabled until parent transport fencing,
restricted browser-reader credential lifecycle, trusted publication and
ACK/result verification are deployed and independently tested.
