# Local network probes

## Purpose

`python -m local_agent.host_ops network` provides two narrow, bounded connectivity facts without turning `host-ops` into a scanner:

```bash
python -m local_agent.host_ops network resolve example.com --json
python -m local_agent.host_ops network tcp 192.168.1.10 22 --timeout 3 --json
```

`resolve` reports deduplicated IPv4/IPv6 addresses for one explicit host. `tcp` attempts one TCP connection to one explicit host/port and reports whether the connection succeeded plus the resolved peer address/family when available.

## Boundary

DNS and socket work runs inside an isolated stdlib worker process controlled by the shared `ProcessRunner`, so the whole operation has a hard deadline and bounded evidence. Host syntax, port range and timeout are validated before execution.

The capability intentionally does not enumerate address ranges, scan port ranges, capture packets, discover services or infer network topology. Those are separate responsibilities and would require their own explicit contract.
