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

## Reproducible authenticated read-only acceptance

On a Mac with an already-authorized GitHub CLI session, run from the
current, exact Local Agent source checkout:

```sh
python -m local_agent.conversation.github_fabric_private_live_smoke --verify-private-synthetic-read
```

This is explicitly opt-in. It uses only `gh api --method GET` against the
hard-coded private repository `MichalMatu/local-agent-fabric-private` and
the `fabric-data` branch. The source code derives a strict bounded
allowlist of GitHub paths; it does not accept a caller-provided URL, workflow,
project, branch, token or raw bootstrap text. It performs two independently
pinned reconstructions and requires equality before reporting a compact
source SHA, dispatch ID, child count and `execution_state=published_execution_unconfirmed`.

The CLI's existing authentication is never copied into environment variables,
the subprocess command line, logs, runtime JSON or ChatGPT prompts. The
adapter discards CLI stderr even for failed requests. A denied/missing or
malformed private GitHub response fails closed.

**Live acceptance evidence, 2026-10-09:** `fabric-data` pinned at
`b834209d99f088e093d503632717ae0aaeafbf7f` was read twice
through the authenticated `gh api` GET-only adapter and returned the
two-child synthetic fixture both times. The Local Agent task
`local-agent-m8-private-real-cold-recovery-gh-api-20261009-v2` completed
with exit code 0. This is evidence for the **private read/recovery slice
only**, not browser restart, child execution, ACK or real user content.
