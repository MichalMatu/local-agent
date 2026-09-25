# Local Agent ChatGPT plugin prototype

This directory contains the private-plugin prototype for using the connected GitHub app as the durable source/control plane while routing execution to the cheapest safe worker.

## Architecture

```text
ChatGPT planner
  -> Local Agent plugin skills
  -> connected GitHub app owned by the user
       |-> direct GitHub source edits
       |-> ChatGPT sandbox + ChatGPT Library offline packs
       |-> GitHub Actions canonical networked CI
       `-> repository agent-control -> Local Agent on the user's computer
```

There is no Local Agent MCP server in this design. GitHub provides the authenticated durable transport. The user's own GitHub account and repositories are used; product users never route their projects through the maintainer's GitHub account.

## Worker selection

Prefer the least machine-specific worker that can produce trustworthy evidence:

1. **GitHub** for bounded source/configuration/documentation edits.
2. **ChatGPT sandbox** for reproducible software-only builds/tests when the repository provides an exact source snapshot and compatible offline dependency pack.
3. **GitHub Actions** for networked dependency resolution and canonical exact-SHA CI.
4. **Local Agent** for attached hardware, local files/data/services, platform-specific behavior, or other evidence that genuinely requires the user's computer.

This keeps routine compilation and test load away from weaker user computers while preserving local execution for the things a remote sandbox cannot reproduce.

## Sandbox and ChatGPT Library

The sandbox itself is ephemeral and may not have package-network access. Repositories can therefore publish reproducible source snapshots and dependency packs through GitHub Actions, then keep the reusable artifacts in ChatGPT Library.

A repository-owned pattern is:

```text
/<Project>/Sandbox/
  <project>-source-<git-sha>.tar.zst
  <project>-source-<git-sha>.tar.zst.sha256
  <project>-offline-<dependency-key>/
    manifest/
    part-00
    part-01
    ...
```

Every sandbox run must verify the exact source SHA and checksums before claiming test/build evidence. Library artifacts are transport/cache only; GitHub remains source of truth.

Current reference implementations:

- `MichalMatu/photomap` — full Python/npm/Playwright sandbox-first flow with split offline packs and exact source snapshots;
- `MichalMatu/tracker` — Android/JDK 21 sandbox flow with Gradle/Android SDK offline caches and Local Agent reserved for physical-device/ADB/Bluetooth evidence.

These are architectural references only. Each product user works with their own repositories and their own GitHub account.

## Private prototype

The private/local package declares the existing GitHub connector in `.app.json` and marks it required. The plugin skills then use GitHub repository reads/writes to operate the established workflow.

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

1. **Private/local validation:** package the Local Agent skills together with the required existing GitHub connector reference.
2. **Public directory candidate:** keep the Local Agent workflow as a skills-only public plugin and require the user to install/connect GitHub separately, unless OpenAI adds public dependency-by-reference support before submission.

The second track preserves the no-MCP architecture.

## Monetization constraint

OpenAI currently prohibits selling digital services or subscriptions inside a published plugin. A plugin may, however, let a user access features from an existing paid account. A future paid Local Agent product should therefore keep billing/account setup outside the plugin and make the plugin consume an already-entitled Local Agent installation/account. The plugin must not initiate or promote a subscription checkout inside ChatGPT.

A license/entitlement service, if added later, is separate from the execution transport. It does not require replacing GitHub with an MCP server.

## Prototype scope

The first milestone now covers both execution lanes:

- require the connected GitHub app;
- select the cheapest safe worker;
- use exact-SHA sandbox snapshots and compatible Library dependency packs for software-only work;
- resolve exact repository identity and `agent_binding` before any Local Agent task;
- inspect daemon/run/result evidence;
- create immutable bounded task files only when local execution is actually needed;
- support exact-task cancellation through the existing Git-backed control plane;
- fail closed on missing/mismatched identity, unavailable GitHub access, or stale/mismatched sandbox inputs;
- keep GitHub as source of truth and canonical CI as the release gate when repository policy requires it.

The existing Local Agent executor, scheduler, watchdog, resource, binding, recovery, and emergency-control implementations are unchanged.
