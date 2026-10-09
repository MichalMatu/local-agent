# No-Bridge CLI: fail-closed GitHub transport errors

The no-Bridge operator CLI supports explicitly enabled, GET-only calls
for synthetic source verification and pinned agent-control history.
GitHub rate limits, authorization denial, timeouts and transport failures
must not propagate raw exception traces or stringified remote responses
to the terminal where credentials or other personal details could surface.

This draft catches the narrow GitHub adapter exceptions already emitted by
the public/private readers: GithubFabricHTTPError and
GithubFabricTransportError. It returns a deterministic nonzero status and
prints only a generic error class identifier. It does not catch unrelated
programming exceptions or silently relabel missing evidence as success.

The test suite exercises an HTTP 403 and a simulated transport exception
whose message contains secret-looking material; neither the fake credential
nor those details may appear in stdout/stderr.

There is no new network capability, no task publication, no Send or ACK,
no automatic retry or live transport switch. This is an error-handling
hardening patch stacked on the read-only source work. Full exact-head Mac
verification and an independent review remain required.
