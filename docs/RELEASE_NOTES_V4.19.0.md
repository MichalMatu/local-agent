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

## Bounded inputs and results

- Bound tool arguments at both entry layers: raw CLI JSON is capped before parsing and the library client independently requires a JSON-serializable object whose canonical serialized form is at most 64 KiB before any network call.
- Bound complete serialized discovery and textual/structured tool results.
- Bound discovery count and pagination.
- Convert image, audio and embedded blob content to atomically written artifact files instead of returning base64 in task output.
- Require explicitly allowed artifact MIME types and enforce aggregate binary size and artifact-count limits.
- Return artifact path, MIME type, byte size and SHA-256 digest as bounded metadata.
- Use the complete SHA-256 digest in deterministic artifact filenames as well as metadata so a shortened hash cannot become the artifact path identity.

## CLI

The packaged interface is:

```bash
python -m local_agent.mcp.cli servers
python -m local_agent.mcp.cli tools <server-id>
python -m local_agent.mcp.cli call <server-id> <tool-name> --arguments '{}'
```

Write and arbitrary-code calls require the matching `--intent` value. Existing Local Agent tasks can call this CLI without a task-schema or scheduler extension. `--registry` is a global option and therefore precedes the subcommand; `--artifact-dir` belongs to the `call` subcommand.

## Re-audit hardening

The pre-release architecture/security re-audit found no need for an application-specific MCP adapter and no scheduler/task-schema change. It did identify two defense-in-depth gaps and closed both before release:

1. the 64 KiB tool-argument bound had been enforced by the CLI but not by direct library callers;
2. deterministic artifact filenames used only the first 16 hexadecimal SHA-256 characters even though full SHA-256 metadata was already returned.

The final boundary now enforces the argument bound inside `call_tool()` before connecting and uses the full SHA-256 digest in artifact filenames. Regression coverage verifies oversized and non-JSON-serializable programmatic arguments fail before network access and verifies full-digest artifact naming.

## Live Fusion 360 evidence

A real Autodesk Fusion 360 MCP server was used as the first external application proof without adding Fusion-specific runtime code. The server listened only on `127.0.0.1:27182`; `/mcp` negotiated MCP protocol `2025-11-25` and identified itself as `MCP Server Adapter` 1.0.0.

Live discovery exposed exactly four tools:

- `fusion_mcp_electronics_read` — read Fusion Electronics design data;
- `fusion_mcp_execute` — execute operations in the active Fusion model;
- `fusion_mcp_read` — read geometric/model/document/project/licensing/screenshot data;
- `fusion_mcp_update` — update the active Fusion model.

Only `fusion_mcp_read` was locally enabled with risk `read`. No write or arbitrary-code smoke was performed. A live `activeCommand` call succeeded with `ok=true`, `is_error=false` and returned Fusion's default `SelectCommand`. A separate 256 x 256 screenshot call returned MCP image content that Local Agent persisted as a real PNG rather than base64 output; the proof file was 878 bytes and its SHA-256 was `f6c9aed9c97ee674686aed4fdb8333683df232d559a817d2e4178f41e0f9ca46`.

That live proof was performed on the generic candidate before the final argument-bound/full-filename hardening. Because those hardening changes touch the same MCP boundary, the release gate requires one final read-only Fusion recheck on the frozen runtime candidate before `main` advances.

## Verification

The candidate adds focused positive/negative registry and policy tests plus a real hermetic Streamable HTTP server integration suite. The HTTP suite exercises SDK discovery/protocol negotiation, read invocation, explicit write/arbitrary-code intent, bounded arguments, connection/call timeouts, malformed responses, oversized text, image artifact persistence, deterministic full-digest naming and size rejection. The MCP suites are included in macOS smoke.

Before release, the exact final candidate still requires the existing full CI matrix and exact-SHA macOS smoke. After runtime hardening is frozen, repeat the live Fusion 360 proof with discovery plus read-only text and image invocation. No application-specific runtime exception is permitted.

## Deployment

Production remains v4.18.26 until the explicit release decision. Before installing 4.19.0 on the production checkout, install `requirements-runtime.txt` into the Local Agent virtual environment so self-update/full verification can execute the MCP tests. Configure MCP servers only in the machine-local registry; no server endpoints or policies belong in Git.
