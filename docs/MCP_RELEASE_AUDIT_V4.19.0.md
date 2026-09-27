# MCP release re-audit — Local Agent 4.19.0

## Scope

This audit reviews the generic MCP boundary introduced for Local Agent 4.19.0 after the first successful live Autodesk Fusion 360 interoperability proof. It covers ownership, transport, authorization, input/output bounds, artifact persistence, dependency/deployment impact, tests, documentation, and release gates.

The reviewed boundary is `local_agent/mcp/` plus `requirements-runtime.txt`, MCP-focused tests, CI/macOS-smoke wiring, and the canonical MCP/release documentation. The Local Agent task schema, repository binding, scheduler, resource admission, daemon control, supervisor process lifecycle, and Chat Bridge protocol are intentionally outside the MCP implementation and remain behaviorally unchanged.

## Architecture conclusion

The architecture remains generic and appropriately isolated.

- `local_agent/mcp/` is the only protocol owner.
- There is no Fusion-, Autodesk-, KiCad-, Blender-, host-ops-, or project-specific runtime branch.
- Streamable HTTP uses the official MCP Python SDK rather than local JSON-RPC/framing code.
- MCP is invoked through a packaged client/CLI from ordinary Local Agent commands; no MCP-specific task or scheduler field was added.
- Stdio remains unsupported because allowing the SDK to spawn a child would bypass Local Agent's registered spawn/process-group lifecycle.
- Server identity and tool authorization come only from explicit machine-local configuration; server discovery metadata is never authority.

No architecture split or application adapter is required for the current release.

## Security and boundedness review

The re-audit confirms the following fail-closed properties:

- endpoints are accepted only for exact loopback hosts `127.0.0.1`, `::1`, or `localhost`;
- the HTTP client runs with environment proxy inheritance disabled;
- unknown or disabled servers fail before connection;
- unknown or disabled tool policies fail before invocation;
- every allowed tool is locally classified as `read`, `write`, or `arbitrary_code`;
- `write` and `arbitrary_code` require exact matching explicit invocation intent;
- discovered tool names, descriptions, schemas, and annotations do not assign risk;
- tool discovery count, discovery metadata, text/structured results, artifact count, and aggregate binary bytes are bounded;
- raw CLI argument JSON is bounded before parsing;
- direct library arguments are independently required to be a JSON object, JSON-serializable, and at most 64 KiB in canonical serialized form before network access;
- image/audio/blob base64 is validated, decoded under configured bounds, MIME allowlisted, and excluded from normal textual output;
- artifacts are written atomically and return absolute path, MIME type, byte size, and full SHA-256 metadata;
- deterministic artifact filenames include the complete SHA-256 digest so the persisted path and returned digest use the same content identity;
- connection and call timeouts remain separately bounded;
- malformed/unsupported protocol content fails closed rather than being guessed or silently coerced.

## Findings closed during re-audit

### AUD-MCP-001 — library callers could bypass the CLI argument-size guard

**Severity:** medium defense-in-depth gap.

The original candidate capped raw CLI `--arguments` input at 64 KiB, but `call_tool()` accepted an already-built Python dictionary without independently serializing and bounding it. A direct library caller could therefore create a request larger than the CLI contract.

**Resolution:** the shared client now validates that arguments are a JSON object, JSON-serializable, and no larger than 64 KiB in canonical serialized form before opening an MCP connection. Invalid arguments use the dedicated `invalid_arguments` boundary error. Tests prove oversized and non-serializable programmatic inputs fail before network access.

### AUD-MCP-002 — deterministic artifact path used a shortened hash prefix

**Severity:** low defense-in-depth gap.

The original candidate returned full SHA-256 metadata but used only the first 16 hexadecimal characters in the filename. The server/tool/index namespace and content prefix made accidental collision unlikely, but the persisted path did not use the same full content identity as the metadata.

**Resolution:** artifact filenames now include the complete SHA-256 digest. Tests assert the full digest is present in the persisted PNG filename.

### AUD-MCP-003 — CLI option placement was easy to misuse

**Severity:** documentation/usability.

`--registry` is a global option while `--artifact-dir` belongs to the `call` subcommand. The first live binary smoke attempted the artifact option at the wrong parser level and was rejected before any Fusion call.

**Resolution:** canonical MCP documentation now shows exact examples for both option positions, and CLI regression coverage asserts `call --help` exposes `--artifact-dir` and `--intent`.

## Live application evidence before final hardening

The first real application proof used Autodesk Fusion 360's local MCP server on `127.0.0.1:27182/mcp` with candidate `2292e69ee4ef346b8fed3f15bed3c65ffbdbc84b`.

The client negotiated MCP `2025-11-25` with `MCP Server Adapter` 1.0.0 and discovered four tools:

1. `fusion_mcp_electronics_read`;
2. `fusion_mcp_execute`;
3. `fusion_mcp_read`;
4. `fusion_mcp_update`.

Only `fusion_mcp_read` was enabled locally with risk `read`. A read-only `activeCommand` invocation returned the active/default Fusion `SelectCommand` with `ok=true` and `is_error=false`. A second read-only screenshot invocation returned MCP image content that was persisted as a 256 x 256 PNG, 878 bytes, SHA-256 `f6c9aed9c97ee674686aed4fdb8333683df232d559a817d2e4178f41e0f9ca46`, without base64 in normal output.

No `fusion_mcp_execute` or `fusion_mcp_update` call was made.

Because AUD-MCP-001 and AUD-MCP-002 changed the MCP runtime after that proof, one final read-only Fusion discovery/text/image recheck is required against the frozen hardened runtime before release.

## Automated verification status

The pre-hardening exact candidate `2292e69ee4ef346b8fed3f15bed3c65ffbdbc84b` passed GitHub Actions run `36282861569`, including:

- compile, Ruff, Bridge validation, and full unittest/integration suite;
- coverage;
- Python 3.14 compatibility;
- Chromium Bridge browser smoke;
- macOS smoke including the real hermetic MCP Streamable HTTP tests.

The hardened candidate must pass the same matrix again after AUD-MCP-001/002/003. This document must not be used to infer success until the final run is recorded below.

## Residual boundaries accepted for 4.19.0

- Only local Streamable HTTP is supported. Remote MCP, OAuth, secret storage, public endpoints, SSE compatibility transport, and stdio remain out of scope.
- Machine-local registry integrity is an operator/host responsibility; Local Agent treats its explicit policy as authority and the MCP server as untrusted data/behavior within that policy.
- A locally authorized `read` tool is trusted not to mutate the application because risk classification is an operator policy decision. Local Agent deliberately does not infer safety from server-provided names or annotations.
- Artifact files persist in Local Agent machine state until normal operator/host cleanup; this release does not add an artifact-retention daemon.
- Runtime dependency deployment remains explicit: `requirements-runtime.txt` must be installed into the production Local Agent virtual environment before advancing production to 4.19.0.

## Final release checklist

Before advancing `main`:

- [ ] hardened candidate CI matrix passes on the exact final source/docs SHA;
- [ ] macOS smoke passes on that exact SHA;
- [ ] final read-only Fusion discovery/text/image recheck passes on the frozen hardened runtime;
- [ ] no write or arbitrary-code live smoke is performed;
- [ ] exact `main...candidate` diff is rechecked for unexpected files or application-specific code;
- [ ] canonical MCP, architecture, operations, Golden Standard, changelog, and release notes are mutually consistent;
- [ ] downstream planner-documentation audit confirms no downstream change is required because task schema/scheduler/Bridge contracts are unchanged;
- [ ] production virtualenv has the pinned runtime dependency before self-update/restart;
- [ ] explicit release decision advances `main`, creates tag `v4.19.0`, and restarts/verifies production;
- [ ] obsolete candidate worktree/branch is removed only after production is established.

## Release decision

**Current status:** candidate hardening complete; final hardened CI and final read-only Fusion recheck pending. Production remains `v4.18.26`.
