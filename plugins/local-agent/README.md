# Local Agent ChatGPT plugin prototype

This directory contains the first private-plugin prototype for using the existing ChatGPT GitHub app as Local Agent's remote control plane.

## Architecture

```text
ChatGPT
  -> Local Agent skill
  -> connected GitHub app
  -> target repository agent-control branch
  -> Local Agent executor on the user's computer
  -> run/result evidence back through GitHub
```

There is no Local Agent MCP server in this design. GitHub provides the authenticated durable transport; Local Agent remains the bounded executor.

## Private prototype

The private/local package declares the existing GitHub connector in `.app.json` and marks it required. The plugin skill then uses GitHub repository reads/writes to operate the established Local Agent control plane.

The repo-local development marketplace is stored at:

```text
.agents/plugins/marketplace.json
```

The plugin package is:

```text
plugins/local-agent/
```

OpenAI's current local-marketplace documentation requires the ChatGPT desktop app for this authoring/test flow. After checking out this candidate branch, add or refresh the repository marketplace in a supported local client and install `local-agent@local-agent-dev` from the Plugins Directory.

## Public distribution constraint

As of 2026-09-25, OpenAI's public plugin submission path does not allow a directory submission to publish an existing integration such as the GitHub connector by reference. Local/workspace packages may reference an eligible registered connector, but public directory submission requires either a skills-only package or a submitted MCP server.

That means the current product plan has two distinct tracks:

1. **Private/local validation:** package the Local Agent skill together with the required existing GitHub connector reference. This is the prototype implemented here.
2. **Public directory candidate:** keep the Local Agent workflow as a skills-only public plugin and require the user to install/connect GitHub separately, unless OpenAI adds public dependency-by-reference support before submission.

The second track preserves the no-MCP architecture. It needs end-to-end validation on a supported public-plugin surface before release because plugin installation itself would not automatically install the GitHub dependency.

## Monetization constraint

OpenAI currently prohibits selling digital services or subscriptions inside a published plugin. A plugin may, however, let a user access features from an existing paid account. A future paid Local Agent product should therefore keep billing/account setup outside the plugin and make the plugin consume an already-entitled Local Agent installation/account. The plugin must not initiate or promote a subscription checkout inside ChatGPT.

A license/entitlement service, if added later, is separate from the execution transport. It does not require replacing GitHub with an MCP server.

## Prototype scope

The first milestone is intentionally narrow:

- require the connected GitHub app;
- resolve exact repository identity and `agent_binding` from `agent-control`;
- inspect daemon/run/result evidence;
- create immutable bounded task files;
- support exact-task cancellation through the existing Git-backed control plane;
- fail closed on missing/mismatched identity or unavailable GitHub write access;
- keep source editing on the normal GitHub path and prefer Local Agent for machine-specific execution/verification.

The existing executor, scheduler, watchdog, resource, binding, recovery, and emergency-control implementations are unchanged.
