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

The current operator setup has already demonstrated the desired ordinary ChatGPT + GitHub + Local Agent workflow without invoking Codex as the local executor. Preserve this architecture, but validate the exact customer/public-plugin surface before making universal quota claims.

## Implemented on this branch

- `plugins/local-agent/plugin.json`
- `plugins/local-agent/.app.json`
- `plugins/local-agent/skills/local-agent-control/SKILL.md`
- `plugins/local-agent/skills/sandbox-execution/SKILL.md`
- `.agents/plugins/marketplace.json`
- `tests/test_chatgpt_plugin_package.py`
- `docs/CHATGPT_PLUGIN_PLAN.md`
- `docs/PLUGIN_PRODUCT_AUDIT_2026-09-25.md`

At the end of this session the branch was 16 commits ahead of `main` and 0 behind before this handoff commit. All branch changes were additive plugin/docs/tests work; Local Agent runtime implementation was not modified.

GitHub reported no combined status checks on the then-current head. Therefore do not treat the candidate as CI-validated yet merely because structural tests are committed.

## Closest market precedents found

- VibeCoder — GitHub as remote control plane for a local/container worker, but execution is delegated to coding-agent CLIs and interaction is issue/PR-driven.
- `chatgpt-use` — explicitly explores ChatGPT subscription capacity separate from Codex/API usage, but delegates execution to other agents or MCP.
- CodexGPT / Chat On Steroids — ChatGPT-to-local-machine outcome through MCP/tunnels rather than GitHub task/result transport.
- AgentControlPlane — web AI to local coding executors.
- Open Interpreter / Interpreter Workstation — general local computer execution/control.
- Hexis / Bevel — Git-backed agent control/configuration plane, enterprise/MCP oriented.

No exact match was found for the combined design: ChatGPT planner + user's existing GitHub integration + deterministic Git-backed Local Agent executor + ChatGPT sandbox/Library lane.

## Commercial note

USD 5/month remains a plausible individual entry price, but support/onboarding economics matter more than compute cost because execution/model infrastructure is mostly user/OpenAI/GitHub-owned. Consider roughly USD 49/year once onboarding is stable. Mainstream comparison points checked during this session included GitHub Copilot Pro at USD 10/month and Cursor Pro at USD 20/month; Cline's individual client is free but model inference is paid/BYOK.

The repository currently has no root `LICENSE` file. Decide deliberately whether the commercial product is proprietary/source-available or uses an explicit open-source license before public launch. Do not describe it as an open-source core until that decision is made.

## Next session

1. Run/trigger verification for the plugin package candidate.
2. Install the repo marketplace plugin in a supported ChatGPT desktop surface.
3. Perform a harmless read-only Local Agent E2E using the user's connected GitHub account.
4. Perform a fresh-chat PhotoMap-style sandbox/Library E2E with exact SHA and offline pack.
5. Test onboarding using a clean second GitHub account/repository so no maintainer-specific identity leaks remain.
6. Design `setup`/`doctor` onboarding only after these two execution lanes are proven from the plugin.
