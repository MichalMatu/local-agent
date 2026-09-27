# Local Agent 4.19.0

## Summary

Add a generic, fail-closed local MCP client boundary owned by `local_agent.mcp`. The initial transport is loopback-only Streamable HTTP through the official MCP Python SDK. No Fusion, KiCad, Blender, hardware-lab, or host-ops-specific runtime code is introduced.

The Local Agent task schema, scheduler, repository binding, resource admission, process lifecycle, daemon control, and Chat Bridge protocol are unchanged.

## Generic MCP boundary

- Add a versioned machine-local MCP server registry under `~/Library/Application Support/local-agent/mcp/servers.json`.
- Accept only `streamable_http` endpoints whose host is exactly `127.0.0.1`, `::1`, or `localhost`.
- Reject unknown/disabled servers and unknown/disabled tool policies before invocation.
- Require explicit matching invocation intent for locally classified `write` and `arbitrary_code` tools.
- Treat server names, descriptions and MCP annotations as untrusted discovery metadata rather than authorization.
- Use the official `mcp==2.2.0` SDK for transport and protocol negotiation instead of implementing JSON-RPC or pinning a protocol revision.
- Keep stdio unsupported so an MCP library cannot spawn a process outside Local Agent's registered process lifecycle.

## Bounded results

- Bound complete serialized discovery and textual/structured tool results.
- Bound discovery count and pagination.
- Convert image, audio and embedded blob content to atomically written artifact files instead of returning base64 in task output.
- Require explicitly allowed artifact MIME types and enforce aggregate binary size and artifact-count limits.
- Return artifact path, MIME type, byte size and SHA-256 digest as bounded metadata.

## CLI

The packaged interface is:

```bash
python -m local_agent.mcp.cli servers
python -m local_agent.mcp.cli tools <server-id>
python -m local_agent.mcp.cli call <server-id> <tool-name> --arguments '{}'
```

Write and arbitrary-code calls require the matching `--intent` value. Existing Local Agent tasks can call this CLI without a task-schema or scheduler extension.

## Verification

The candidate adds focused positive/negative registry and policy tests plus a real hermetic Streamable HTTP server integration suite. The HTTP suite exercises SDK discovery/protocol negotiation, read invocation, explicit write/arbitrary-code intent, connection/call timeouts, malformed responses, oversized text, image artifact persistence and size rejection. The MCP suites are included in macOS smoke.

Before release, the exact final candidate still requires the existing full CI matrix and exact-SHA macOS smoke. The first live Fusion 360 proof is a separate read-only release evidence step: record the actual loopback endpoint and tool list, invoke only policy-classified read tools, and verify artifact handling if the server emits image content. No application-specific runtime exception is permitted.

## Deployment

Production remains v4.18.26 until the explicit release decision. Before installing 4.19.0 on the production checkout, install `requirements-runtime.txt` into the Local Agent virtual environment so self-update/full verification can execute the MCP tests. Configure MCP servers only in the machine-local registry; no server endpoints or policies belong in Git.
