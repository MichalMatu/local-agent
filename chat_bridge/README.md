# Local Agent Chat Bridge

Chrome Manifest V3 extension that schedules bounded autonomous wake-ups for multiple explicitly configured ChatGPT conversations. The bridge remains transport only: ChatGPT plans work and `local-agent` executes deterministic tasks.

The canonical planner/executor contract is documented in `docs/AUTONOMOUS_CHAT_LOOP.md`, `docs/OPERATIONS.md` and `docs/MULTI_REPOSITORY.md`.

## v0.5 delivery and hard-binding model

Chat Bridge v0.5 uses state schema v3 and makes repository routing explicit, immutable conversation identity:

```text
one ChatGPT conversation == one agent_binding UUID == one repository id == one GitHub repository
```

- multiple conversations can be enabled at the same time;
- every conversation has an independent alarm, status, interval override and assistant-control dedupe state;
- every configured conversation stores `repositoryId`, `repository`, `agentBinding`, `bindingRevision` and `bindingSetAt`;
- normal edits cannot change those binding fields;
- repository identity can change only through the explicit **Rebind** action;
- unbound migrated conversations are disabled with `binding_required` and receive no alarm;
- runtime/catalog mismatch disables a conversation with `binding_catalog_mismatch` rather than guessing a replacement;
- `STOP`, `PAUSE`, `RESUME`, `INTERVAL` and `NEXT` affect only the conversation that emitted the marker;
- a global master switch can suspend scheduling without deleting per-conversation state or bindings.

Chrome must remain running and each scheduled conversation must remain open in a tab. The tab does not need to be foregrounded.

## Binding envelope and wake flow

Every bootstrap and compact wake is prefixed with the exact stored identity:

```text
[LA_AGENT=<canonical UUID>]
[LA_REPO=<repository id>]
[LA_REPOSITORY=<owner/name>]
[LA_CHAT=<conversation id>]
```

The planner must use that identity as a routing boundary. It must not switch repositories from remembered context. If the active goal really needs another repository, it should pause until the operator explicitly Rebinds the conversation.

Newly bound or explicitly rebound conversations receive one bootstrap prompt. After the bootstrap is sent successfully, ordinary wake-ups use the compact wake prompt.

The default compact prompt is intentionally short:

```text
[LA_WAKE] Continue the active Local Agent goal from exact target-repo evidence. Do not recap unchanged state; keep this wake terse.
```

Remote runtime schema v3 publishes pacing plus the canonical agent catalog:

```json
{
  "schema_version": 3,
  "interval_minutes": 10,
  "busy_retry_minutes": 1,
  "bootstrap_prompt": "...",
  "wake_prompt": "...",
  "agents": [
    {
      "repository_id": "matrixhub",
      "repository": "MichalMatu/MatrixHub",
      "agent_binding": "033327ab-700d-43b4-9b3b-caff1acaa2c7",
      "execution_enabled": true
    }
  ]
}
```

Repository ids, repositories and binding UUIDs must each be unique. Binding UUIDs use canonical lowercase UUID text. Only runtime schema v3 is accepted. `execution_enabled` must be a JSON boolean. An unavailable/invalid catalog blocks sending as `runtime_unavailable`; no built-in catalog replaces it.

The `local-agent` catalog entry has `execution_enabled: false`. It exists for bridge/operator infrastructure conversations; it must not be used to create project tasks.

The service worker keeps a short in-memory runtime-config cache so simultaneous conversations do not refetch the same remote runtime file unnecessarily.

## Executor-side protection

Bridge routing is not the only guard. Local Agent independently requires before task claim/execution:

```text
local repository registry agent_binding
    == <control checkout>/.agent/binding.json agent_binding
    == task.agent_binding
```

Both the production parallel worker and serial fallback enforce this contract. Missing repository binding blocks admission as `unbound`; control mismatch blocks as `binding_error`; missing/wrong task binding is terminally rejected before any task command runs.

The global Local Agent operator `disabled` marker has higher priority than binding admission and remains the rollout/emergency safety boundary.

## Conversation-scoped control protocol

A bridge command is accepted only when it is the final non-empty line of the latest assistant message in that exact configured conversation.

Preferred compact markers:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:NEXT=30s]
[LAB:NEXT=10m]
[LAB:INTERVAL=30m]
[LAB:INTERVAL=AUTO]
```

Legacy markers remain valid:

```text
[LOCAL_AGENT_BRIDGE:STOP]
[LOCAL_AGENT_BRIDGE:PAUSE]
[LOCAL_AGENT_BRIDGE:RESUME]
[LOCAL_AGENT_BRIDGE:NEXT=30s]
[LOCAL_AGENT_BRIDGE:INTERVAL=30]
[LOCAL_AGENT_BRIDGE:INTERVAL=AUTO]
```

Semantics:

- `STOP` disables only that conversation and clears its persistent interval override.
- `PAUSE` disables only that conversation while preserving its interval override.
- `RESUME` re-enables that conversation and schedules a near-term busy-retry wake; it never changes the binding.
- `NEXT=<duration>` arms or re-arms that conversation and schedules its next wake without changing the normal interval. It never overrides the global master switch. Durations are bounded to 30 seconds through 24 hours.
- `INTERVAL=<minutes>` sets that conversation's persistent interval override.
- `INTERVAL=AUTO` removes the override and returns to runtime/default pacing.

No assistant marker can perform Rebind. Binding changes are explicit operator UI actions only.

Control dedupe is stored per conversation. Rebind clears conversation control dedupe state and forces the next send to be a fresh bootstrap.

## Popup configuration

The extension popup provides:

- a global master scheduler switch;
- one-click **Add current chat** for the active ChatGPT conversation;
- automatic conversation id/URL extraction, including project-scoped ChatGPT conversation URLs;
- automatic initial label from the browser tab title;
- explicit agent/repository selection when binding a conversation;
- one card per configured conversation with its immutable binding identity, editable label, enable/pause, manual interval override, `Run now`, save, **Rebind** and remove actions;
- per-conversation last status, next wake and bootstrap/compact-wake mode;
- global runtime URL, default interval, busy retry, compact wake prompt and bootstrap prompt.

Normal card edits preserve the binding. Rebind is intentionally separate so changing a label, interval or enable state cannot silently redirect a conversation to another Local Agent repository.

## Migration from older bridge state

Existing schema-v2 conversations do not have trustworthy repository identity. On first v0.4 startup they migrate as disabled/unbound with `binding_required`; the bridge does not infer routing from their label, URL or old chat context.

Bind each intended conversation explicitly before re-enabling its schedule. A rebound conversation receives a new binding revision and a fresh bootstrap.

## Install/update from the local-agent checkout

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the repository's `chat_bridge` directory.
4. Open a concrete ChatGPT conversation. Standard `/c/<id>` links and project-scoped links ending in `/c/<id>` are supported.
5. Open the extension, click **Add current chat**, and select the exact Local Agent repository/agent identity.
6. Repeat for other conversations.
7. Use **Run now** on a bound conversation card for an end-to-end wake test.

After updating an already loaded unpacked extension, click **Reload** on its `chrome://extensions` card. Existing pre-v0.4 conversations intentionally require explicit binding before they can schedule again.

Bridge 0.5 requires Chrome 120 or newer. Reload open ChatGPT tabs after reloading the extension so they use the matching delivery protocol. Existing schema-v3 bindings remain intact. A pending or unconfirmed wake pauses as `delivery_uncertain`; inspect the chat and use **Wake was sent** or **Wake was not sent** before explicitly resuming. Neither resolution sends a message. Rebind and removal are blocked until delivery is resolved.

## Choose GitHub or local execution

The planner may read and edit the bound repository directly through an available GitHub tool with the required permissions. Use this path for bounded source, configuration or documentation changes when review of the exact diff and relevant CI checks can verify the result. A GitHub commit proves a change, not successful execution; report the exact commit and completed checks.

Use Local Agent when the action needs command execution on the Mac, local build/test tools, device access or other machine-specific evidence. A hybrid flow may commit through GitHub and then queue a read-only verification task for that exact source SHA. Check the bound repository's active task first and avoid concurrent writes to the same branch while a local task is modifying it. Follow the repository's own branch policy.

Every local task still requires a unique immutable id, the exact `agent_binding`, explicit `resources` and bounded execution. Direct GitHub edits do not require an artificial executor task merely to record that they happened. The immutable conversation binding applies to both paths. The `local-agent` catalog entry remains unavailable for project execution; infrastructure edits follow its release policy.

## Development validation

```bash
python scripts/verify.py --only bridge
npm install --no-save --package-lock=false playwright@1.57.0
npx playwright install chromium
python scripts/verify.py --profile bridge-browser
```

Browser smoke uses a disposable Chromium profile, an offline conversation fixture and the actual extension. It verifies delivery confirmation, draft preservation, SPA navigation, overlap, uncertain delivery and service-worker restart without using the operator's browser or sending live chat messages. Set `LOCAL_AGENT_PLAYWRIGHT_MODULE` to an existing Playwright module path when reusing installed test tooling.
