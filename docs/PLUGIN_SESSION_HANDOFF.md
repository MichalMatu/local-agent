# Local Agent plugin session handoff

Date: 2026-09-25
Branch: `feature/chatgpt-plugin-github-control-plane`

## Frozen product direction

User-owned architecture:

```text
ChatGPT
  -> Local Agent plugin skills
  -> user's connected GitHub account
  -> user's repositories
  -> direct GitHub edits / GitHub Actions / ChatGPT sandbox + Library / Local Agent
```

GitHub is the durable control plane and source of truth. Customer repositories and GitHub authorization belong to the customer; work must never be routed through the maintainer's GitHub account.

Use ChatGPT sandbox + persistent Library offline packs for reproducible software-only build/test work when the active surface supports it. Use GitHub Actions for networked dependency/bootstrap generation and canonical CI. Use Local Agent only for machine-specific execution such as hardware, local files/services, platform-specific state, or missing sandbox-compatible toolchains.

The normal product architecture does not require a public Local Agent MCP execution endpoint, inbound remote shell, tunnel or maintainer-operated execution broker. Do not add one as a convenience shortcut without an explicit product/security decision.

The current operator setup has already demonstrated the desired ordinary ChatGPT + GitHub + Local Agent workflow without invoking Codex as the local executor. Preserve this architecture, but validate the exact customer/public-plugin surface before making universal quota claims.

## Product invariants to preserve

- user-owned GitHub only;
- exact repository/source/binding identity before execution;
- GitHub remains source of truth;
- Library is cache/transport, never source of truth;
- sandbox is preferred for reproducible software-only work but is never assumed to exist;
- Local Agent is reserved for genuinely local or hardware-specific evidence;
- no secrets or private machine state in reusable Library packs;
- fail closed on missing authorization, stale packs, unsupported capabilities or binding mismatch;
- no public quota/model claims until validated on the exact customer-facing surface.

The detailed canonical product plan is `docs/CHATGPT_PLUGIN_PLAN.md`.

## Implemented on this branch

- `plugins/local-agent/plugin.json`
- `plugins/local-agent/.app.json`
- `plugins/local-agent/skills/local-agent-control/SKILL.md`
- `plugins/local-agent/skills/sandbox-execution/SKILL.md`
- `.agents/plugins/marketplace.json`
- `tests/test_chatgpt_plugin_package.py`
- `docs/CHATGPT_PLUGIN_PLAN.md`
- `docs/PLUGIN_PRODUCT_AUDIT_2026-09-25.md`
- `docs/PLUGIN_SESSION_HANDOFF.md`

All branch changes produced in this plugin session are additive plugin/docs/tests work; Local Agent runtime implementation was intentionally not modified.

Do not preserve a hard-coded "N commits ahead" number in this handoff because it becomes stale as soon as the branch changes. At the start of the next session, compare the candidate branch against `main` and inspect the exact head before doing any further work.

No combined CI status was available on the candidate head during this session. Therefore do not treat the candidate as CI-validated merely because structural tests are committed.

## Closest market precedents found

- VibeCoder — GitHub as remote control plane for a local/container worker, but execution is delegated to coding-agent CLIs and interaction is issue/PR-driven.
- `chatgpt-use` — explicitly explores ChatGPT subscription capacity separate from Codex/API usage, but delegates execution to other agents or MCP.
- CodexGPT / Chat On Steroids — ChatGPT-to-local-machine outcome through MCP/tunnels rather than GitHub task/result transport.
- AgentControlPlane — web AI to local coding executors.
- Open Interpreter / Interpreter Workstation — general local computer execution/control.
- Hexis / Bevel — Git-backed agent control/configuration plane, enterprise/MCP oriented.

No exact match was found for the combined design during this research pass: ChatGPT planner + user's existing GitHub integration + deterministic Git-backed Local Agent executor + ChatGPT sandbox/Library lane. Treat that as a dated research result, not a permanent uniqueness claim.

## Commercial note

USD 5/month remains a plausible individual entry-price hypothesis, with roughly USD 49/year worth testing once onboarding is stable. Support/onboarding economics matter more than compute cost because execution/model infrastructure is mostly user/OpenAI/GitHub-owned.

The repository currently has no root `LICENSE` file. Decide deliberately whether the commercial product is proprietary, source-available, open-source with a paid product layer, or dual-licensed before public launch. Do not describe it as open source until a specific license is present and reviewed.

## Next session

1. Compare `feature/chatgpt-plugin-github-control-plane` against current `main`; inspect exact head and ensure no unexpected runtime changes appeared.
2. Run the plugin package structural tests and the narrowest relevant repository verification before claiming the candidate is healthy.
3. Install the repo marketplace plugin in a supported ChatGPT desktop surface.
4. Perform a harmless read-only Local Agent E2E using the user's connected GitHub account.
5. Perform a fresh-chat PhotoMap-style sandbox/Library E2E with exact SHA and offline pack.
6. Test onboarding using a clean second GitHub account/repository so no maintainer-specific identity leaks remain.
7. Only after both execution lanes are proven, design/implement `local-agent setup` and `local-agent doctor` around observed failure modes.
8. Re-check current OpenAI plugin distribution/commerce rules before any public-submission work.

Do not merge this candidate into `main` merely because the planning/docs package is complete. Merge remains a separate explicit release decision after the candidate has real verification evidence.
