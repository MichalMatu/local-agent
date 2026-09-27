# MCP release re-audit — Local Agent 4.19.0

## Scope

This audit records the generic MCP boundary released in Local Agent 4.19.0 after the first successful live Autodesk Fusion 360 interoperability proof and the final hardening pass. It covers ownership, transport, authorization, input/output bounds, artifact persistence, dependency/deployment impact, tests and release evidence.

The reviewed boundary is `local_agent/mcp/` plus `requirements-runtime.txt`, MCP-focused tests, CI/macOS-smoke wiring, and canonical MCP/release documentation. Local Agent task schema, repository binding, scheduler, resource admission, daemon control, supervisor process lifecycle and Chat Bridge protocol remained unchanged in 4.19.0.

## Architecture conclusion

The released architecture is generic and isolated:

- `local_agent/mcp/` is the only MCP protocol owner;
- there is no Fusion-, Autodesk-, KiCad-, Blender-, host-ops-, or project-specific runtime branch;
- Streamable HTTP uses the official MCP Python SDK instead of local JSON-RPC/framing code;
- ordinary Local Agent commands invoke the packaged client/CLI, so no MCP-specific task or scheduler field was added;
- stdio remains unsupported because an SDK-spawned child would bypass Local Agent's registered process lifecycle;
- server identity and tool authorization come only from explicit machine-local configuration; discovery metadata is never authority.

No application adapter or architecture split was required for this release.

## Security and boundedness

The released boundary is fail closed:

- only exact loopback hosts `127.0.0.1`, `::1`, and `localhost` are accepted;
- HTTP proxy inheritance is disabled;
- unknown or disabled servers and tools fail before invocation;
- every allowed tool is locally classified `read`, `write`, or `arbitrary_code`;
- `write` and `arbitrary_code` require exact matching explicit invocation intent;
- server-provided names, descriptions, schemas and annotations do not assign risk;
- discovery count/metadata, textual/structured output, artifact count and aggregate binary bytes are bounded;
- CLI and direct-library tool arguments are independently bounded before network access;
- image/audio/blob data is MIME-validated, bounded, atomically persisted and represented in normal output by path/MIME/size/SHA-256 metadata rather than base64;
- deterministic artifact filenames include the complete SHA-256 digest;
- connection and call timeouts are separately bounded;
- malformed or unsupported protocol content is rejected rather than guessed.

## Findings closed before release

### AUD-MCP-001 — direct library callers could bypass the CLI argument-size guard

The original candidate bounded raw CLI arguments but did not independently bound an already-built Python argument object. `call_tool()` now requires a JSON object whose canonical serialized form is at most 64 KiB before opening a connection. Invalid programmatic input uses the `invalid_arguments` boundary error, with regression coverage proving failure before network access.

### AUD-MCP-002 — artifact path used a shortened digest prefix

The original candidate returned full SHA-256 metadata but used only the first 16 hexadecimal characters in deterministic filenames. The final implementation uses the complete digest in the persisted filename and metadata; tests verify that identity.

### AUD-MCP-003 — CLI option placement was ambiguous

`--registry` is global while `--artifact-dir` belongs to the `call` subcommand. Canonical documentation and CLI regression coverage now make this placement explicit.

## Live Fusion 360 evidence

The first real application proof used Autodesk Fusion 360's local MCP server at `127.0.0.1:27182/mcp`. The client negotiated MCP `2025-11-25` with `MCP Server Adapter` 1.0.0 and discovered four tools:

1. `fusion_mcp_electronics_read`;
2. `fusion_mcp_execute`;
3. `fusion_mcp_read`;
4. `fusion_mcp_update`.

Only `fusion_mcp_read` was enabled locally with risk `read`. A read-only `activeCommand` call succeeded. A read-only screenshot returned MCP image content persisted as a 256 x 256 PNG, 878 bytes, SHA-256 `f6c9aed9c97ee674686aed4fdb8333683df232d559a817d2e4178f41e0f9ca46`, without base64 in normal output. No execute/update write smoke was performed.

Because the argument and artifact hardening changed runtime code after the initial proof, the same read-only boundary was rechecked on exact hardened runtime SHA `143e0c8817400b2bf993fe33eef4b21da2c356b7`. Discovery returned the same four tools; policy still enabled only `fusion_mcp_read`; `activeCommand` succeeded; the PNG screenshot succeeded with the same byte size and digest; and the complete digest appeared in the persisted filename.

## Automated verification

The hardened candidate `143e0c8817400b2bf993fe33eef4b21da2c356b7` passed GitHub Actions run `36288336646` across compile/Ruff/full tests, coverage, Python 3.14, Chromium Bridge browser smoke and macOS smoke including the hermetic MCP Streamable HTTP suite.

The final release source commit `1ea863d06a20e766f9fe0fa5589cc59aa0e2671a` also received a successful full pull-request workflow run (`36290273277`) before release.

## Release record

Local Agent 4.19.0 is released.

- `main` release commit: `1ea863d06a20e766f9fe0fa5589cc59aa0e2671a`;
- annotated release tag: `v4.19.0`;
- published live Local Agent repository status observed daemon version `4.19.0` at that exact self revision, using the parallel multi-repository worker and reporting idle state;
- v4.19.0 is the production baseline immediately preceding the 4.19.1 planner-scope candidate.

The historical post-release push workflow on the same `main` SHA later reported a documentation/release-state failure; that does not invalidate the previously successful exact-source candidate verification or the observed deployed runtime, but it exposed stale release-state prose. The 4.19.1 checkpoint corrects that documentation drift rather than rewriting runtime history.

## Residual boundaries accepted for 4.19.0

- Only local Streamable HTTP is supported. Remote MCP, OAuth, secret storage, public endpoints, SSE compatibility transport and stdio remain out of scope.
- Machine-local registry integrity remains an operator/host responsibility.
- A locally authorized `read` tool is trusted not to mutate the application because risk classification is explicit operator policy; Local Agent does not infer safety from server metadata.
- Artifact retention remains ordinary machine-state cleanup; 4.19.0 does not add an artifact-retention daemon.
- Runtime dependencies remain explicit production installation state through `requirements-runtime.txt`.

## Final status

The 4.19.0 release gate is closed. Runtime implementation, hardening, architecture/security review, full candidate CI/macOS verification, final read-only Fusion interoperability proof, release tag and deployed daemon identity are established. Subsequent planner-scope behavior is versioned separately as the 4.19.1 candidate.
