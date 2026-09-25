# ChatGPT plugin plan

Status: candidate work on `feature/chatgpt-plugin-github-control-plane`.

Market/product research snapshot: [`PLUGIN_PRODUCT_AUDIT_2026-09-25.md`](PLUGIN_PRODUCT_AUDIT_2026-09-25.md).

Session continuation handoff: [`PLUGIN_SESSION_HANDOFF.md`](PLUGIN_SESSION_HANDOFF.md).

## Goal

Expose the established Local Agent Git-backed control plane as a ChatGPT plugin workflow without adding a Local Agent MCP execution server, while using the ChatGPT sandbox as the preferred software-only execution worker when a repository provides reproducible offline inputs.

The intended architecture is:

```text
ChatGPT planner
    -> Local Agent plugin skills
    -> existing connected GitHub app owned by the user
         |-> direct GitHub edits
         |-> ChatGPT sandbox + ChatGPT Library cache
         |-> GitHub Actions canonical networked CI
         `-> repository agent-control -> Local Agent executor on user's computer
```

GitHub remains the source of truth and durable transport. The user's own GitHub account/repositories are used; customer work must never be routed through the maintainer's GitHub account.

The Local Agent executor remains unchanged and retains hard binding, immutable tasks, bounded process execution, resource admission, watchdogs, recovery, and emergency controls.

## Product positioning

The product is not another hosted coding model and should not be positioned as one.

The product value is the orchestration layer that lets a customer reuse resources they already have:

- their ChatGPT subscription as the planner/conversation surface;
- their own GitHub account as the durable authenticated control plane and source of truth;
- the ChatGPT sandbox + Library for reproducible software-only compute when available;
- GitHub Actions for networked bootstrap/dependency generation and canonical CI;
- their own computer through Local Agent only when local state, platform-specific behavior or hardware is genuinely required.

The already proven operator setup does not invoke Codex as the executor in its normal ChatGPT + GitHub + Local Agent loop. Preserve that architecture, but validate the exact customer-facing plugin surface and plan before making broad quota/usage claims in marketing.

Adjacent products exist, but the current market audit did not find an exact match for the full combination of ordinary ChatGPT planning, user-owned GitHub control, deterministic bound local execution, and a ChatGPT sandbox/Library lane. Treat the competitor analysis in `PLUGIN_PRODUCT_AUDIT_2026-09-25.md` as a living research document, not as proof of uniqueness forever.

## Established sandbox references

Two repositories already demonstrate the intended sandbox lane.

### PhotoMap

`MichalMatu/photomap` is the most complete reference implementation:

- `docs/SANDBOX_EXECUTION_FLOW.md` defines sandbox-first worker selection;
- GitHub Actions creates an exact source snapshot for the target SHA;
- optional offline packs contain Python wheelhouse, npm cache, and Playwright Chromium;
- dependency keys derive from lockfiles/toolchain/bootstrap inputs;
- large packs are split into Library-friendly parts with SHA-256 manifests;
- fresh sandboxes reconstruct a venv and `node_modules` from offline caches;
- GitHub remains source of truth and canonical CI remains the release gate;
- Local Agent is reserved for genuinely machine-specific evidence.

### Tracker

`MichalMatu/tracker` applies the same model to Android:

- exact source snapshots;
- JDK 21 / Gradle / Android SDK offline caches;
- isolated sandbox Gradle state;
- GitHub Actions as canonical networked Android worker;
- Local Agent/Mac reserved for ADB, physical phone, Bluetooth, screen-off/permission, and other hardware/runtime evidence.

These implementations are references, not product dependencies. Product users must be able to apply the same pattern to their own repositories.

## Worker-selection policy

The product should choose the cheapest safe worker that can produce the required evidence:

1. direct GitHub for bounded source/configuration/documentation changes;
2. ChatGPT sandbox for reproducible software-only builds/tests when exact source and compatible offline dependencies are available;
3. GitHub Actions for networked dependency resolution, offline-pack generation, and canonical exact-SHA CI;
4. Local Agent only for local files/data/services, platform-specific behavior, attached hardware, or other evidence that genuinely requires the user's computer.

This makes Local Agent useful both to powerful-workstation users and to users with weak computers: routine compute can be shifted into the ChatGPT sandbox while hardware/local-state work stays on the user's machine.

## Sandbox/Library contract

A fresh sandbox must be treated as ephemeral and potentially offline.

For every sandbox run:

- resolve the exact repository and target Git SHA;
- use a matching source snapshot from ChatGPT Library or trusted GitHub Actions artifact;
- verify checksum before extraction when provided;
- verify embedded SHA after extraction;
- restore only a dependency pack whose dependency key matches repository/toolchain inputs;
- run repository-owned bootstrap/doctor/check wrappers rather than inventing another test system;
- run focused checks before broad checks;
- never upload secrets, signing material, production databases, cookies, tokens, local `.env` files, or private machine state into Library packs;
- treat Library artifacts as cache/transport only, never source of truth.

If Library/file access is unavailable on the active ChatGPT surface, the skill must not pretend the cache is available. Use GitHub Actions artifacts/CI or Local Agent according to repository policy.

## Confirmed platform facts on 2026-09-25

1. OpenAI plugins may contain reusable skills, connected apps, or both.
2. Local/workspace plugin packages may reference an eligible registered connector in `.app.json`. The existing ChatGPT GitHub app is currently exposed as an eligible connector and can therefore be required by the private prototype.
3. Local plugin marketplaces are supported by the ChatGPT desktop app and are suitable for private authoring/testing.
4. Public directory submission currently does **not** allow third-party publishers to publish an existing integration by reference. Public submission either accepts a skills-only package or requires the publisher to submit its own MCP server.
5. A public skills-only Local Agent plugin can preserve the no-MCP architecture if GitHub is installed/connected separately and the skill fails closed when GitHub write access is unavailable.
6. Plugin commerce currently does not allow selling digital subscriptions inside the plugin. Users may access an existing paid account/entitlement. Any future Local Agent billing and entitlement flow must therefore live outside the ChatGPT plugin surface.
7. The already proven GitHub-backed Local Agent flow uses ordinary ChatGPT conversation planning and local execution rather than Codex execution. The plugin product must preserve that architecture where the target ChatGPT surface supports the same workflow; do not generalize quota claims to untested surfaces.

## Phase 0 - private package scaffold

Implemented in this candidate branch:

- `plugins/local-agent/plugin.json` portable Agent Plugins manifest;
- `plugins/local-agent/.app.json` required GitHub connector mapping;
- `plugins/local-agent/skills/local-agent-control/SKILL.md` Git-backed Local Agent control workflow;
- `plugins/local-agent/skills/sandbox-execution/SKILL.md` sandbox/Library worker workflow;
- `.agents/plugins/marketplace.json` repository-local development marketplace;
- structural package regression tests.

No executor/runtime behavior changes are part of Phase 0.

## Phase 1 - private end-to-end validation

Use an isolated candidate checkout/worktree. Do not move the production `~/local-agent` checkout away from `main` merely to test the plugin.

Validate both lanes in the ChatGPT client.

### Sandbox lane

1. Resolve an explicitly selected repository and exact source SHA.
2. Detect repository sandbox instructions when present.
3. Retrieve/materialize the matching source snapshot from Library or trusted CI artifact.
4. Verify source checksum and embedded SHA.
5. Restore the exact compatible dependency pack.
6. Run the repository sandbox doctor/bootstrap.
7. Run one focused software-only test/build without using the user's Mac.
8. Report exact source SHA and executed evidence.
9. Confirm that stale/mismatched snapshot or dependency pack fails closed.

### Local Agent lane

1. The repo marketplace is discovered.
2. `local-agent@local-agent-dev` installs.
3. Installation recognizes the required GitHub connection.
4. A read-only prompt reads one explicitly selected repository's `agent-control` state.
5. The skill refuses a missing/unauthorized repository instead of guessing.
6. The skill reads the exact `.agent/binding.json` before any task write.
7. The skill creates one immutable read-only task with exact binding and explicit `resources`.
8. Local Agent claims and executes that task on the user's computer.
9. The same conversation reads the exact terminal `.agent/results/<task-id>.json` and reports it correctly.
10. A second task for the same active goal is not queued while the first is active.
11. Exact-task `cancel_task` is tested with remote ACK plus terminal cancellation evidence.

### Independent-customer validation

Before making public claims, repeat the end-to-end flow on a clean second account/environment that does not inherit the maintainer's current setup:

- a different GitHub account or organization;
- a newly authorized repository;
- a fresh plugin install;
- a fresh Local Agent installation;
- a fresh sandbox/Library setup where applicable;
- no maintainer-specific repository ids, paths, bindings or credentials.

This test must prove that the product is genuinely user-owned and portable rather than accidentally dependent on the original development environment.

## Phase 2 - repository onboarding

Turn the current hand-built repository integrations into a portable product contract.

A repository should be able to opt into one or both execution lanes:

- **sandbox profile:** repository-owned `docs/SANDBOX_EXECUTION_FLOW.md`, `tools/sandbox/` wrappers, dependency-key definition and optional `sandbox-pack.yml` generator;
- **Local Agent profile:** `agent-control`, exact `agent_binding`, daemon/status/task/result contract.

Future onboarding tooling should inspect the repository and generate only the missing pieces. It must not overwrite an existing project-specific sandbox or Local Agent policy.

The onboarding experience is a commercial requirement, not optional polish. The target experience is approximately:

```text
local-agent setup
  -> authenticate/verify GitHub
  -> choose repository
  -> inspect existing project instructions
  -> provision only missing Local Agent control-plane state
  -> detect or bootstrap optional sandbox profile
  -> verify plugin/GitHub access
  -> run a harmless read-only end-to-end task
  -> READY
```

Add a companion `local-agent doctor` command that produces actionable diagnostics for GitHub authorization, repository binding, daemon state, runtime dependencies, sandbox prerequisites and common platform-specific failures.

Support cost is a pricing constraint: a low-cost subscription is viable only if setup and diagnosis are usually self-service. Avoid a product model that requires routine manual debugging of PATH, Python, permissions, launchd/services or GitHub state for each customer.

## Phase 3 - workflow hardening

After live E2E succeeds:

- add representative worker-routing evaluation prompts;
- verify that ordinary software-only work chooses sandbox rather than local execution when both are available;
- test direct GitHub edit + sandbox focused verification + exact-SHA CI as the default software path;
- test direct GitHub edit + sandbox/CI + Local Agent device verification as the hybrid hardware path;
- document recovery when Library cache is missing/stale;
- document recovery when GitHub write succeeds but the local executor is offline;
- document recovery when a task is accepted but terminal evidence is delayed;
- preserve the rule that worker-specific evidence proves only what that worker actually executed;
- add product-level diagnostics that explain why a worker was selected or rejected;
- test degraded operation when sandbox access, GitHub Actions, Local Agent, or Library is individually unavailable.

## Phase 4 - public skills-only candidate

Create a separate public packaging profile that excludes `.app.json` and therefore does not publish the GitHub connector by reference.

The public skill must:

- state GitHub as a prerequisite without pretending installation grants it;
- use GitHub when available;
- use the ChatGPT sandbox/Library lane only when those capabilities are actually available on the active surface;
- stop with a clear prerequisite message when required access is unavailable;
- never fall back to an untrusted alternate transport;
- retain exact repository/binding/source-SHA safety semantics.

Public-release validation must explicitly confirm the target ChatGPT surface, model availability, GitHub write behavior, sandbox/Library availability and actual usage/quota behavior. Do not assume private/local plugin behavior automatically carries over to the public directory surface.

## Phase 5 - product and entitlement

The execution transport should remain GitHub-backed unless evidence shows a real need for another transport.

If Local Agent becomes a paid product, use an external account/license flow for the Local Agent installation. The ChatGPT plugin may recognize an existing entitlement but must not sell or promote a digital subscription inside the plugin under current OpenAI policy.

A small entitlement service may be added later, but it is independent of GitHub transport and is not an MCP requirement.

Initial pricing hypothesis:

- individual target: approximately **US$5/month**;
- annual target to evaluate: approximately **US$49/year**;
- future team/business tiers only after the individual workflow is validated.

These are hypotheses, not committed prices. Validate willingness to pay, churn, payment fees and support burden before locking pricing.

The main economic advantage is that Local Agent should not pay for the customer's model inference or routine build compute. The customer supplies ChatGPT, GitHub, GitHub Actions quota, sandbox availability and/or their own hardware. Our recurring infrastructure should remain mostly account/licensing/update/support infrastructure rather than a hosted execution farm.

## Phase 6 - licensing and distribution decision

There is currently no root `LICENSE` file. Before public distribution, make an explicit product/legal choice rather than accidentally implying open-source rights.

Evaluate at least these models:

- proprietary commercial distribution;
- source-available core with commercial-use restrictions;
- open-source core plus paid convenience/product layer;
- dual licensing where appropriate.

The chosen model should protect the ability to monetize installer/onboarding, updates, plugin packaging, support and commercial convenience without preventing useful community adoption.

Do not advertise the project as open source until a specific license is present and reviewed.

## Phase 7 - commercial validation

Before treating the product as ready to monetize:

1. onboard at least one genuinely independent user/account without maintainer intervention;
2. measure install-to-first-success time;
3. measure how often `setup` and `doctor` solve problems without manual support;
4. validate both sandbox-first and Local-Agent-required workflows;
5. verify no customer repository traffic is routed through maintainer-owned GitHub infrastructure;
6. confirm current OpenAI plugin publishing and commerce rules again immediately before submission;
7. validate the claim about avoiding Codex execution on the exact public customer surface before using it in sales copy;
8. collect failure categories and use them to improve onboarding before adding more features;
9. test a small paid beta before committing to a final subscription price.

The primary commercial risk is not compute cost; it is support/onboarding cost and dependence on platform behavior outside Local Agent's control. Optimize product work accordingly.

## Release boundary

This plugin work is additive infrastructure. Do not change Local Agent runtime behavior, task schema, binding semantics, or downstream project instructions merely to satisfy plugin packaging. Any future change to those contracts must follow the normal candidate-release, verification, downstream-audit, and versioning rules in `AGENTS.md`.
