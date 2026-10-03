# Local Agent 4.20.3

## Scope

This release adds one narrow Conversation Fabric DEV-lab migration needed after the 4.20.2 isolated-profile adoption: safely rebind an already adopted but still unused lab marker from its original isolated checkout identity to a dedicated isolated operator checkout.

Chat Bridge remains 0.7.0. Operator intake remains default-disabled. This release does not onboard a Superchat, enable operator intake, start a child campaign, or mutate production/daily Chrome.

## Change

`python -m local_agent.development.lab rebind-checkout` is fail-closed and may update only the lab marker when all of the following are true:

- the requested root and new checkout remain disjoint from production paths;
- the new checkout already exists as a regular non-symlink directory;
- the current `lab.json` is a canonical marker for the existing layout;
- the existing lab reports healthy against that current marker;
- `state`, `repositories`, `logs`, and `fixtures` are all empty;
- the requested new layout is otherwise valid.

On success only `lab.json` is atomically replaced with the new canonical layout. The browser profile is not copied, rewritten, removed, or traversed for mutation.

## Operational purpose

The already adopted isolated profile lives at:

```text
~/Library/Application Support/local-agent-dev-stage8-cf-manual/browser-profile
```

The intended stable operator checkout is:

```text
~/local-agent-conversation-operator
```

4.20.3 provides the supported path to align the durable lab marker with that dedicated checkout without manually editing or deleting safety metadata.

## Verification boundary

The release requires focused positive/negative rebind tests plus the normal exact-SHA release gates. Production remains Local Agent 4.20.2 until an explicit release decision advances `main` and the running daemon is verified on the released revision.
