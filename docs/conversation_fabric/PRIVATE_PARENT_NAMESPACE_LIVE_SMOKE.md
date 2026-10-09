# Private parent namespace: real authenticated GET-only absence smoke

Status: **explicit opt-in observation**, no private write, no browser authority.

This command uses only the existing trusted Mac `gh` authenticated session:

```sh
python -m local_agent.conversation.github_fabric_private_live_smoke --verify-private-parent-namespace-empty
```

It performs two independent observations of the same fixed private repository
`MichalMatu/local-agent-fabric-private`, branch `fabric-data`. Each pass
resolves the exact commit SHA, Git commit tree and complete recursive tree
through a strict read-only allowlist. Truncated/invalid/oversized trees,
unexpected `parents/` entries and unexpected parent index/record presence
fail closed. A changed origin SHA between reads also fails.

The successful JSON contains only the source SHA,
`status=no_parent_records_observed`, `reads=2`,
`browser_effects_permitted=false`, and `ack_state=not_attested`.

**Important:** This is a bounded **absence check** for the current
unactivated namespace, not a reader of populated parent-fence records.
If `parents/index.json` or `parents/parent-*.json` exists, the command
requires explicit review and does not pretend that ownership or browser
child execution has been verified. PR #209/#214 are separate synthetic
parent-fence drafts, not production transport gates.

No credential is exposed to ChatGPT, a content script, command arguments,
stored runtime config or logs; `gh` supplies its already authenticated
session. All requests are GitHub API GET. No browser tabs, composer
population, Send, child ACK or task execution occur.

The deterministic fake-adapter tests are in
`tests/test_github_fabric_private_parent_namespace_smoke.py`.
