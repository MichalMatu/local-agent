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

The pre-release architecture/security re-audit found no need for an application-specific MCP adapter and no scheduler/task-schema change. It identified two defense-in-depth gaps and one usability ambiguity, all closed before release:

1. the 64 KiB tool-argument bound had been enforced by the CLI but not by direct library callers;
2. deterministic artifact filenames used only the first 16 hexadecimal SHA-256 characters even though full SHA-256 metadata was already returned;
3. CLI documentation did not make the global/subcommand placement of `--registry` and `--artifact-dir` sufficiently explicit.

The final boundary enforces the argument bound inside `call_tool()` before connecting, returns the dedicated `invalid_arguments` boundary error for invalid programmatic input, and uses the full SHA-256 digest in artifact filenames. Regression coverage verifies oversized and non-JSON-serializable programmatic arguments fail before network access, full-digest artifact naming, and CLI option placement.

## Live Fusion 360 evidence

Autodesk Fusion 360's local MCP server was used as the first real external application proof without adding Fusion-specific runtime code. The server listened only on `127.0.0.1:27182`; `/mcp` negotiated MCP protocol `2025-11-25` and identified itself as `MCP Server Adapter` 1.0.0.

Live discovery exposed exactly four tools:

- `fusion_mcp_electronics_read` — read Fusion Electronics design data;
- `fusion_mcp_execute` — execute operations in the active Fusion model;
- `fusion_mcp_read` — read geometric/model/document/project/licensing/screenshot data;
- `fusion_mcp_update` — update the active Fusion model.

Only `fusion_mcp_read` was locally enabled with risk `read`. No write or arbitrary-code smoke was performed.

After final hardening, the full read-only proof was repeated on exact runtime SHA `143e0c8817400b2bf993fe33eef4b21da2c356b7`:

- discovery again negotiated MCP `2025-11-25` and returned the same four tools;
- local policy showed `fusion_mcp_read` configured/enabled as risk `read`, with `fusion_mcp_execute` and `fusion_mcp_update` unconfigured/disabled;
- `activeCommand` succeeded with `ok=true`, `is_error=false` and returned Fusion's default `SelectCommand`;
- a 256 x 256 screenshot returned MCP image content that Local Agent persisted as a real PNG rather than base64 output;
- the PNG was 878 bytes with SHA-256 `f6c9aed9c97ee674686aed4fdb8333683df232d559a817d2e4178f41e0f9ca46`;
- the complete SHA-256 appeared in the persisted filename, proving the hardened artifact identity path on a real application.

## Verification

The candidate includes focused positive/negative registry and policy tests plus a real hermetic Streamable HTTP server integration suite. The HTTP suite exercises SDK discovery/protocol negotiation, read invocation, explicit write/arbitrary-code intent, bounded arguments, connection/call timeouts, malformed responses, oversized text, image/blob artifact persistence, deterministic full-digest naming and size/MIME rejection. The MCP suites are included in macOS smoke.

Hardened runtime SHA `143e0c8817400b2bf993fe33eef4b21da2c356b7` passed GitHub Actions run `36288336646` across compile/Ruff/full tests, coverage, Python 3.14, Chromium Bridge browser smoke, and macOS smoke. The final live Fusion read-only recheck also passed on that exact runtime SHA.

Documentation-only release-evidence commits after the frozen runtime SHA require one final exact-SHA CI pass before `main` advances. See `MCP_RELEASE_AUDIT_V4.19.0.md` for the complete release gate record.

## Deployment

Production remains v4.18.26 until the explicit release decision. Before installing 4.19.0 on the production checkout, install `requirements-runtime.txt` into the Local Agent virtual environment so self-update/full verification can execute the MCP tests. Configure MCP servers only in the machine-local registry; no server endpoints or policies belong in Git.
