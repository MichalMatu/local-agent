# Local Agent plugin product and market audit — 2026-09-25

Status: research snapshot for `feature/chatgpt-plugin-github-control-plane`.

## Product architecture under evaluation

The intended user-owned architecture is:

```text
ChatGPT
  -> Local Agent plugin skills
  -> user's connected GitHub account
  -> user's repository / agent-control branch
  -> worker selection
       -> ChatGPT sandbox + ChatGPT Library for reproducible software-only work
       -> GitHub Actions for networked dependency/bootstrap generation and canonical CI
       -> Local Agent on the user's computer for machine-specific execution
  -> evidence returned through GitHub / the active ChatGPT conversation
```

No Local Agent-owned public MCP execution server is required for the private/local prototype. GitHub is the authenticated durable control plane and repository source of truth. The user's computer remains outbound-only with respect to normal repository task transport.

The current operator deployment has already demonstrated the important product property that its normal ChatGPT + GitHub + Local Agent loop does not invoke Codex as the executor. Treat that as operator-verified evidence for the current setup, not yet as a universal claim for every future ChatGPT plan, model, surface, or public-plugin rollout. Validate the exact customer surface before marketing quota behavior broadly.

## Current implementation state

The candidate branch contains:

- portable `plugins/local-agent/plugin.json`;
- private/local `.app.json` mapping the existing GitHub connector;
- `local-agent-control` skill for bound GitHub-backed Local Agent execution;
- `sandbox-execution` skill for exact-SHA, offline-cache sandbox work;
- repository-local marketplace metadata;
- structural regression coverage;
- product/implementation plan in `docs/CHATGPT_PLUGIN_PLAN.md`.

The runtime executor itself is intentionally unchanged by this plugin scaffold.

## Platform fit confirmed from current OpenAI documentation

As of 2026-09-25:

1. Plugins may be skills-only, MCP-only, or skills plus MCP.
2. Skills can work without an MCP server when packaged instructions/resources are sufficient.
3. Local/workspace packages may reference an eligible registered integration in `.app.json`; the private prototype can therefore depend on the user's connected GitHub integration.
4. Public directory submission cannot publish an already-existing integration by reference. A public Local Agent submission should therefore be skills-only unless Local Agent later submits its own remote MCP server.
5. A skills-only public package can still instruct the model to use separately installed/connected GitHub tooling, but this must be validated end-to-end on the intended public ChatGPT surface.
6. Current plugin commerce policy does not allow selling digital subscriptions from inside the plugin or promoting a checkout. A plugin may recognize and use an existing paid entitlement created outside ChatGPT.

Primary references:

- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/plugins/build/skills
- https://developers.openai.com/plugins/deploy/submission
- https://developers.openai.com/plugins/deploy/submission-errors
- https://developers.openai.com/plugins/app-guidelines

## Existing and adjacent projects

No project found in this audit matches the complete Local Agent combination exactly: ordinary ChatGPT as planner, the user's existing GitHub integration as the durable control plane, deterministic bound local execution, plus a ChatGPT-sandbox/Library execution lane.

There are, however, several important adjacent competitors and design precedents.

### Open Interpreter / Interpreter Workstation

Open Interpreter lets language models run code and control a computer locally. Interpreter Workstation provides a local/remote computer workspace and model-provider flexibility. It is a strong competitor for the broad promise of "AI can use my computer", but it is not centered on the same GitHub-branch task/result protocol or the same ChatGPT-plugin + user-owned GitHub architecture.

Reference:

- https://github.com/openinterpreter/interpreter-workstation
- https://github.com/openinterpreter/open-interpreter

### CodexGPT / Chat On Steroids

These projects connect ChatGPT to a local machine using MCP, typically through a public HTTPS/Tunnel path. They are close in user outcome — ChatGPT can inspect/edit/run locally — but materially different in transport and trust boundary. Local Agent's proposed product avoids operating a public MCP execution endpoint by using GitHub as the remote transport.

References:

- https://github.com/chatGPT-10/codexgpt
- https://github.com/wxh0/gpt-chat

### chatgpt-use

`chatgpt-use` explicitly targets use of a ChatGPT web subscription as a planner/backend without Codex billing, and discusses separate ChatGPT and Codex/API usage buckets. It is therefore the closest conceptual precedent for the quota/value proposition. Its architecture delegates execution to Codex/Claude Code or exposes MCP tools; it does not use the same immutable GitHub control branch plus Local Agent executor model.

Reference:

- https://github.com/leeguooooo/chatgpt-use

### VibeCoder

VibeCoder is an unattended issue-to-PR worker where GitHub is the normal remote control plane and execution happens on a user-managed host/container using Claude Code, Codex CLI, Gemini CLI, or another agent. This is the closest precedent for the "GitHub is the control plane; no inbound host port is required" concept. Its interaction model is GitHub Issues/PRs and the local worker delegates reasoning/editing to coding-agent CLIs, whereas Local Agent keeps ChatGPT as the planner and its local runtime deterministic/non-LLM.

Reference:

- https://github.com/stSoftwareAU/VibeCoder

### AgentControlPlane and other local-agent routers

Projects such as `Ya-KARAS/AgentControlPlane` route web-AI conversations into local Codex/Claude/OpenCode/Kimi executors. They prove market interest in bridging web AI to local coding, but they are executor-router products rather than the same GitHub-backed deterministic execution substrate.

Reference:

- https://github.com/Ya-KARAS/AgentControlPlane

### Hexis / Bevel

Hexis is a Git-backed control plane for agent skills, tools, context, permissions, and identity. It validates Git as a desirable auditable storage/control primitive, but it is aimed at enterprise agent configuration/governance and remains MCP-native rather than being a ChatGPT-to-local deterministic execution product.

Reference:

- https://github.com/Bevel-Software/Hexis

### OpenHands, Cline, Cursor, GitHub Copilot

These are broader coding-agent competitors. Their existence proves strong demand but also means Local Agent should not be marketed as merely "another AI coding agent". The differentiation is transport, execution economics, user-owned infrastructure, and deterministic local/sandbox verification.

Current pricing references checked during this audit:

- GitHub Copilot Pro: USD 10/month; Pro+: USD 39/month; Max: USD 100/month.
- Cursor Pro: USD 20/month; higher individual tiers are substantially more expensive.
- Cline open-source individual client: free; users pay model inference/BYOK costs.

References:

- https://github.com/features/copilot/plans
- https://cursor.com/pricing
- https://cline.bot/pricing

## Differentiation that appears defensible

The strongest product position is not "better coding model". Local Agent does not own the model.

The strongest position is:

1. **Bring your own GitHub** — customer repository and authorization remain theirs.
2. **No inbound execution server required for the GitHub path** — the local daemon consumes Git-backed tasks rather than exposing a general remote shell.
3. **Deterministic executor boundary** — planner and execution authority are separated; task identity, binding, limits, watchdogs, results and recovery are first-class.
4. **Three-worker routing** — sandbox for cheap software-only work, GitHub Actions for networked/canonical CI, Local Agent only when the actual computer/hardware is needed.
5. **Reuse of an existing ChatGPT conversation as planner** — in the current operator setup, local execution is not a Codex executor session. This is a major practical value proposition, but must be revalidated on the final supported customer surfaces before being advertised as a universal quota guarantee.
6. **Low infrastructure cost for the vendor** — the expensive compute largely belongs to ChatGPT, GitHub, the sandbox surface, GitHub Actions, or the customer's own machine rather than a Local Agent cloud fleet.

## Monetization assessment

### USD 5/month is plausible as an entry price

USD 5/month is materially below mainstream coding-agent subscriptions such as GitHub Copilot Pro and Cursor Pro. That makes it easy to understand as an add-on for someone who already pays for ChatGPT and GitHub rather than as another full AI subscription.

Simple gross recurring-revenue scenarios before taxes, payment fees, support and refunds:

| Paying users | MRR at USD 5 | ARR at USD 5 |
| ---: | ---: | ---: |
| 100 | USD 500 | USD 6,000 |
| 1,000 | USD 5,000 | USD 60,000 |
| 5,000 | USD 25,000 | USD 300,000 |
| 10,000 | USD 50,000 | USD 600,000 |
| 25,000 | USD 125,000 | USD 1.5M |
| 100,000 | USD 500,000 | USD 6M |

The product does not need massive scale to become meaningful. Roughly 1,000 paying users would already be a real small software business; 5,000-10,000 paying users would be significant if support and infrastructure remain lean.

### Pricing risk

USD 5 is attractive but creates two problems:

- fixed payment-processing and tax/VAT overhead consume a larger share of a small monthly charge;
- local setup, GitHub authorization, build-toolchain differences and hardware support can create expensive support tickets relative to USD 5 MRR.

A likely stronger commercial structure is:

- free/private beta while onboarding is still technical;
- individual plan around USD 5/month or approximately USD 49/year once setup is reliable;
- higher team/business tier later for managed policy, fleet administration, audit/export, centralized entitlement and priority support.

Do not build the team tier before individual onboarding is demonstrably low-touch.

### Where the paid value must live

The plugin skills alone are easy to inspect and conceptually copy. The paid product should therefore be more than a prompt bundle. Durable value should come from some combination of:

- polished cross-platform installer and automatic updates;
- safe repository provisioning/binding;
- automatic sandbox-pack/Library onboarding;
- diagnostics and self-repair;
- multi-repository administration;
- signed releases and release channels;
- product-grade permission UX;
- entitlement-backed convenience features;
- support and maintained compatibility with ChatGPT/GitHub changes.

The GitHub repository currently has no root `LICENSE` file. Public source without a license is not the same as an open-source grant. Decide the licensing/commercial model deliberately before public launch; do not accidentally promise "open source core" unless an explicit license is chosen.

## Main commercial risks

1. **Platform dependency.** OpenAI can change plugin surfaces, permissions, plan availability, quotas or public-directory rules. GitHub can change connector capabilities. Keep the Git-backed protocol independently usable so the product is not trapped behind one UI.
2. **Quota marketing risk.** The current deployment's non-Codex execution behavior is valuable evidence, but claiming "does not consume Codex limits" for all customers requires testing the exact public surface and plan combinations.
3. **Support cost.** Cross-platform local execution is harder to support than a pure cloud SaaS. Installer, doctor command and reproducible diagnostics are core product work, not polish.
4. **Security perception.** "Give ChatGPT access to my computer" is powerful but scary. The deterministic task contract, explicit repository binding, bounded commands, local kill switch and Git audit trail should be front-and-center.
5. **Public plugin dependency limitation.** The private package can require the registered GitHub integration, while public submission currently cannot bundle that existing integration by reference. Public onboarding must clearly guide the user to connect GitHub separately unless OpenAI changes this policy.
6. **Sandbox availability.** ChatGPT Library/sandbox capabilities can be surface-dependent. The plugin must fail closed/fall back to GitHub Actions or Local Agent when Library/sandbox access is unavailable.
7. **Cloneability.** GitHub-as-control-plane is not itself a moat. The moat is reliability, onboarding, safety, cross-platform execution, sandbox routing, diagnostics and accumulated compatibility/evidence.

## Product verdict

Potential: **high enough to justify continued development and a real beta**, but not yet proven enough to justify revenue forecasts beyond scenario planning.

The market clearly pays USD 10-20+ per month for coding-agent products, while several open-source alternatives prove that developers also value local control and BYOK. A USD 5 add-on can occupy a distinct price/value position if it genuinely lets existing ChatGPT users turn their own GitHub + computer + sandbox into a dependable execution system without purchasing another model-inference subscription from Local Agent.

The concept is differentiated, but the durable business advantage will come from execution quality and onboarding rather than the architectural idea alone.

## Recommended next milestones

1. Install the current candidate plugin from the local marketplace and perform a private end-to-end read-only task.
2. Validate that the skill uses the connected user's GitHub account and never assumes the developer's GitHub identity.
3. Validate PhotoMap-style sandbox execution through a fresh chat: exact source SHA, Library/offline pack restore, focused test, result.
4. Build a productized `setup`/`doctor` path that provisions a new customer's repository with minimal manual Git knowledge.
5. Test on a clean second GitHub account and a clean second computer before calling the flow user-owned/product-ready.
6. Recruit a very small external beta cohort before adding billing.
7. Measure onboarding time, task success rate, support minutes per user and repeat weekly usage. These metrics determine whether USD 5/month is sustainable.
8. Re-check OpenAI public plugin and commerce rules immediately before submission because the platform is changing quickly.
