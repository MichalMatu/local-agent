# Local MCP integration

`local_agent.mcp` is the Local Agent-owned boundary for connecting deterministic tasks to explicitly configured local Model Context Protocol servers. It is generic infrastructure: application-specific workflows and adapters belong to the project that consumes Local Agent, not to this package.

## Supported boundary

The initial transport is MCP Streamable HTTP through the official Python SDK. A configured endpoint is accepted only when its URL host is exactly `127.0.0.1`, `::1`, or `localhost`; non-loopback hosts fail closed during registry parsing. The current boundary does not support remote MCP, OAuth, secret storage, public-network endpoints, SSE compatibility transport, or stdio.

Stdio is deliberately excluded. Local Agent requires every child process to pass through its registered spawn and process-group lifecycle owner. A future stdio transport may be added only if the MCP subprocess is integrated with that lifecycle contract instead of allowing the SDK to spawn an unregistered child.

The runtime dependency is pinned in `requirements-runtime.txt`. The SDK owns MCP framing, discovery/initialize compatibility, session behavior, and protocol negotiation. Local Agent does not implement JSON-RPC or select one protocol revision itself.

## Machine-local registry

The default registry is:

```text
~/Library/Application Support/local-agent/mcp/servers.json
```

It is machine-local state and must not be committed to project repositories. Registry version 1 has this shape:

```json
{
  "version": 1,
  "servers": [
    {
      "id": "local-app",
      "transport": "streamable_http",
      "endpoint": "http://127.0.0.1:8765/mcp",
      "enabled": true,
      "connect_timeout_seconds": 10,
      "call_timeout_seconds": 30,
      "max_text_bytes": 65536,
      "max_artifact_bytes": 8388608,
      "max_tools": 128,
      "max_artifacts": 8,
      "allowed_artifact_mime_types": ["image/png"],
      "tools": [
        {"name": "inspect_state", "risk": "read", "enabled": true},
        {"name": "update_state", "risk": "write", "enabled": false}
      ]
    }
  ]
}
```

Server ids are stable canonical machine identities. The current working directory is never used to infer a server identity. Duplicate ids and duplicate tool policies are rejected.

## Authorization model

Tool discovery is not execution authorization. Every invocation is checked against the machine-local policy before a network call is made:

- unknown server: deny;
- disabled server: deny;
- unknown tool policy: deny;
- disabled tool policy: deny;
- `read`: allowed without additional intent, or with exact `read` intent;
- `write`: requires policy risk `write` and explicit invocation intent `write`;
- `arbitrary_code`: requires policy risk `arbitrary_code` and explicit invocation intent `arbitrary_code`.

Server-provided names, descriptions and MCP tool annotations are discovery metadata only. They are not trusted to determine the local risk class.

Before an authorized call, Local Agent lists the server tools and requires the exact configured tool to be exposed. Discovery count and serialized metadata are bounded before invocation.

Tool arguments are also a protocol-boundary input, not merely a CLI concern. The CLI rejects raw argument JSON above 64 KiB before parsing, and the library client independently requires a JSON-serializable object whose canonical serialized form is at most 64 KiB before any MCP network call. Direct Python callers therefore cannot bypass the CLI bound.

## Bounded results and artifacts

Text and structured JSON remain inline only when the complete structured Local Agent result fits `max_text_bytes`. Oversized discovery or tool results fail closed rather than being silently truncated.

Binary `ImageContent`, `AudioContent`, and blob embedded resources are never returned as base64 in normal CLI output. Their MIME type must be explicitly allowed by the server configuration. Base64 is validated, decoded size and aggregate binary size are bounded by `max_artifact_bytes`, and artifact count is bounded by `max_artifacts`.

The default artifact root is:

```text
~/Library/Application Support/local-agent/mcp/artifacts/
```

Each artifact uses a deterministic filename derived from server id, tool name, content index and the full SHA-256 digest. It is written atomically and returned only as metadata containing absolute path, MIME type, byte size and the same full SHA-256 digest. Using the complete digest in both path and metadata avoids a shortened-hash path collision becoming an overwrite identity.

## CLI contract

The packaged operator interface emits JSON and may be invoked directly or from an ordinary Local Agent task:

```bash
python -m local_agent.mcp.cli servers
python -m local_agent.mcp.cli tools <server-id>
python -m local_agent.mcp.cli call <server-id> <tool-name> --arguments '{"key":"value"}'
python -m local_agent.mcp.cli call <server-id> <tool-name> --intent write --arguments '{}'
```

Use `--registry <path>` only for an explicit alternate machine-local registry. Because it is a global CLI option it precedes the subcommand, for example:

```bash
python -m local_agent.mcp.cli --registry /path/to/servers.json tools <server-id>
```

`call` accepts `--artifact-dir <path>` as a subcommand option, for example:

```bash
python -m local_agent.mcp.cli --registry /path/to/servers.json call --artifact-dir /path/to/artifacts <server-id> <tool-name> --arguments '{}'
```

Otherwise the canonical Local Agent artifact directory is used.

This interface intentionally does not alter the Local Agent task schema or scheduler. The normal path is:

```text
Local Agent task
  -> packaged MCP CLI/client
  -> configured loopback MCP server
  -> bounded structured result/artifact metadata
  -> existing task result capture
```

## Verification

Focused coverage must preserve registry validation, duplicate ids, loopback rejection, unknown/disabled server and tool policy, explicit write/arbitrary-code intent, bounded JSON-serializable arguments at both CLI and client boundaries, connection and call timeouts, malformed responses, bounded discovery, bounded text, binary artifact persistence, MIME/size rejection, full-digest deterministic artifact naming, normal invocation, and SDK protocol negotiation.

Transport evidence uses a real hermetic loopback Streamable HTTP MCP server from the official SDK, not only mocks. The same tests are included in the macOS smoke profile.

A live application smoke is separate evidence. For the first Fusion 360 proof, configure its discovered loopback endpoint in the machine-local registry, run discovery, preserve the real tool list as evidence, and invoke only policy-classified read tools. If an image is returned, verify the persisted artifact MIME, byte size and full SHA-256 digest. Do not run write or arbitrary-code tools during that first smoke. No Fusion-specific exception belongs in `local_agent.mcp`.

A second standards-compliant application such as KiCad should require only another registry entry and policy; needing runtime application code is evidence that this generic boundary should be re-evaluated.
