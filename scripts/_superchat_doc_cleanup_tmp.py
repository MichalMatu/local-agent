from __future__ import annotations

import re
from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"missing expected text in {path}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


def replace_regex(path: str, pattern: str, new: str) -> None:
    text = read(path)
    updated, count = re.subn(pattern, new, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"expected one regex match in {path}, got {count}: {pattern!r}")
    write(path, updated)


# Repository rules and top-level README.
replace_regex(
    "AGENTS.md",
    r"- Chat Bridge conversations must never infer repository identities.*?without changing the conversation binding\.\n",
    "- Chat Bridge conversation identity is transport/scheduling identity only. It never grants repository execution authority and normal repository routing must not depend on chat Rebind.\n"
    "- Repository ids named in the active user goal or durable Conversation Fabric request are reasoning context. A parent Superchat may reason across donor and target repositories without rebinding; every executable Local Agent task still uses the exact canonical binding of its actual target repository.\n"
    "- Runtime `planner_scope` and legacy conversation binding metadata remain compatibility/transport-workspace metadata only. They are not authorization evidence for repository work.\n"
    "- The `local-agent` catalog entry remains `execution_enabled: false` and must never receive executable project work. It may still be inspected or edited through allowed GitHub operations while another execution-enabled target owns any required `.agent/tasks`.\n",
)
replace_once(
    "AGENTS.md",
    "- Hard-binding or planner-scope releases additionally require positive/negative coverage proving normal repository scope remains isolated, multirepo scope resolves only catalog targets, target task bindings remain exact, and parallel/serial executor binding admission is unchanged.",
    "- Transport/repository-routing releases additionally require positive/negative coverage proving chat metadata cannot grant execution authority, selected target task bindings remain exact, execution-disabled targets remain non-executable, and parallel/serial executor binding admission is unchanged.",
)
replace_regex(
    "README.md",
    r"A ChatGPT conversation always keeps one canonical Bridge binding\..*?before work may be claimed\.",
    "A ChatGPT conversation is a Bridge transport/scheduling identity, not a repository authorization boundary. The active goal may use multiple donor/target repositories without rebinding the chat. Local Agent independently validates the actual target repository's registry binding, control binding and task binding before executable work may be claimed.",
)
replace_once(
    "README.md",
    "- immutable Chat Bridge conversation binding with fail-closed repository or explicit multirepo planner scope;",
    "- transport-only Chat Bridge conversation identity with repository-agnostic reasoning scope;",
)

# Security model.
replace_once(
    "docs/SECURITY_MODEL.md",
    "1. **Bridge → planner authorization** — one immutable conversation binding carries a validated planner scope. Normal scope is one repository; explicit `multirepo` scope may select only current runtime-catalog targets. Repository identities and binding UUIDs are never inferred from natural-language context.",
    "1. **Bridge → planner transport** — one concrete conversation identity owns delivery/scheduling only. Repository reasoning scope comes from the active goal or durable request; Bridge metadata never grants repository execution authority.",
)
replace_regex(
    "docs/SECURITY_MODEL.md",
    r"Chat Bridge conversation identity is not inferred from model context\..*?See \[`HOST_OPS_MULTIREPO\.md`\]\(HOST_OPS_MULTIREPO\.md\)\.",
    "Chat Bridge conversation identity is transport/scheduling identity only. A parent Superchat may reason across multiple repositories, including donor and target repositories, without changing Bridge metadata. Natural-language repository names or durable `repository_id` / `repository_ids` fields are reasoning context, never executor authorization.\n\nFor executable work, the selected target must still resolve to a registered repository whose registry binding, `.agent/binding.json` binding and task `agent_binding` agree exactly. Execution-disabled targets cannot receive Local Agent tasks. Legacy `planner_scope` and conversation binding metadata may remain for compatibility or transport-workspace selection but are not security boundaries. See [`HOST_OPS_MULTIREPO.md`](HOST_OPS_MULTIREPO.md).",
)
replace_once(
    "docs/SECURITY_MODEL.md",
    "The Bridge likewise fails closed on unknown planner scopes, invalid multirepo authorization or runtime-catalog mismatch. Multirepo planner authorization is not accepted as substitute evidence for a target repository binding.",
    "Bridge schedule/delivery validation remains fail closed for invalid conversation or control state, but Bridge repository metadata is not executor authorization. No chat state is accepted as substitute evidence for the target repository binding.",
)
replace_once(
    "docs/SECURITY_MODEL.md",
    "- keep repository bindings, planner scopes and the local registry intentional and unique;",
    "- keep repository bindings and the local registry intentional and unique; treat Bridge planner-scope/binding metadata as compatibility state only;",
)

# Golden Standard: current release wording and planner section.
replace_regex(
    "docs/GOLDEN_STANDARD.md",
    r"This file records the current release/runtime invariants.*?never infer the deployed revision from a source checkout alone\.",
    "This file records the current release/runtime invariants for `MichalMatu/local-agent`. The prepared source release is `v4.20.5` with Chat Bridge `0.8.1`; deployed production remains `v4.20.4` until the explicit release merge/tag and live self-update proof. A managed conversation is a transport/scheduling channel rather than a repository execution binding. Repository reasoning may span donor/target repositories without chat rebinding; executable `.agent/tasks` still require the exact canonical binding of the actual target repository. Conversation Fabric operator intake remains explicit runtime configuration, child chats remain reasoning-only, and `.agent/tasks` retains all machine execution authority. Read the installed `self_revision` from live daemon status; never infer the deployed revision from a source checkout alone.",
)
replace_regex(
    "docs/GOLDEN_STANDARD.md",
    r"### Planner scope\n.*?(?=### GitHub-backed schedule/status authority)",
    "### Superchat repository scope\n\n"
    "- Every managed conversation has one concrete chat identity used for Bridge transport and GitHub-backed scheduling.\n"
    "- The chat is not hard-bound to a repository for reasoning. The active user goal or durable Conversation Fabric request may name multiple donor and target repositories without Rebind.\n"
    "- `repository_id` / `repository_ids` in reasoning requests are context only; they do not create machine authority.\n"
    "- Legacy `planner_scope`, `repositoryId`, `agentBinding` and `bindingRevision` fields may remain in migrated Bridge state or the runtime catalog for compatibility/transport-workspace selection. They must not be interpreted as repository authorization.\n"
    "- Before any executable work, resolve the actual target repository and create `.agent/tasks` only with that target's exact canonical `agent_binding`.\n"
    "- Execution-disabled catalog targets may be inspected/reasoned about through allowed GitHub operations but may not receive Local Agent tasks; `local-agent` remains intentionally self-execution-disabled.\n"
    "- A planner must never invoke/delegate local Codex or another local coding-agent/LLM CLI through Local Agent.\n\n",
)
replace_once(
    "docs/GOLDEN_STANDARD.md",
    "Every schedule mutation increments `control_generation`; status reads do not. Repository/binding/revision mismatches fail closed. Applied state is scoped to binding revision, remote control generation and local conversation generation.",
    "Every schedule mutation increments `control_generation`; status reads do not. Schedule ownership is keyed by exact chat identity plus remote control generation and local conversation generation. Legacy repository/binding/revision fields are not schedule authority.",
)
replace_once(
    "docs/GOLDEN_STANDARD.md",
    "A confirmed `conversation_exhausted` state is terminal for the same hard binding and must not be repaired away as GitHub schedule drift.",
    "A confirmed `conversation_exhausted` state is terminal for that conversation safety epoch and must not be repaired away as GitHub schedule drift.",
)
replace_once(
    "docs/GOLDEN_STANDARD.md",
    "Binding controls (`ADD`, `REBIND`, `REMOVE`) and Bridge maintenance remain explicit migration paths until separately moved to a reviewed GitHub control contract.",
    "Legacy binding controls (`ADD`, `REBIND`) remain compatibility/migration paths only and must not be used for normal repository routing. `REMOVE` and Bridge maintenance remain explicit local controls.",
)
replace_once(
    "docs/GOLDEN_STANDARD.md",
    "`docs/HOST_OPS_MULTIREPO.md` is the canonical planner-scope extension.",
    "`docs/HOST_OPS_MULTIREPO.md` is the canonical transport-only multirepo planner guide.",
)

# Operations: keep hard binding where it matters; remove chat-binding authorization story.
replace_regex(
    "docs/OPERATIONS.md",
    r"Repository binding is operational identity\..*?See \[`HOST_OPS_MULTIREPO\.md`\]\(HOST_OPS_MULTIREPO\.md\)\.",
    "Repository binding is operational execution identity. Do not rotate a UUID to repair a task. Chat Bridge conversation metadata is not repository authorization: a parent Superchat may reason across donor and target repositories without Rebind. Every Local Agent task still uses the exact canonical binding of the selected target repository, and executor configuration changes still require an intentional disabled migration.\n\nThe `local-agent` catalog entry remains `execution_enabled: false`: a Superchat may inspect or edit `MichalMatu/local-agent` through direct GitHub operations, but it must not queue a Local Agent task targeting that execution-disabled entry. See [`HOST_OPS_MULTIREPO.md`](HOST_OPS_MULTIREPO.md).",
)
replace_regex(
    "docs/OPERATIONS.md",
    r"## Chat Bridge schema-3 rollout\n.*?(?=## Control data)",
    "## Chat Bridge schema-3 transport/control\n\n"
    "Bridge state may still contain legacy repository/binding fields (`repositoryId`, `repository`, `agentBinding`, `bindingRevision`, `bindingSetAt`) for migration compatibility and epoch/race protection. They are not normal repository-routing or execution-authorization fields. New Superchat onboarding is repository-agnostic.\n\n"
    "Remote runtime schema 3 publishes the repository catalog plus optional compatibility `planner_scope` metadata and `conversation_controls`. For an exact `conversation_controls` record, GitHub desired state is authoritative for STATUS/PAUSE/RESUME/NEXT/INTERVAL and every schedule mutation increments `control_generation`. Schedule ownership is keyed by chat identity, not repository/binding revision. Assistant LAB schedule markers are legacy no-ops for managed chats. Production runtime is served from branch `chat-bridge-state`, file `chat_bridge/runtime.json`. See [`GITHUB_BRIDGE_CONTROL.md`](GITHUB_BRIDGE_CONTROL.md).\n\n"
    "Rollout checks for Bridge changes must prove: concrete conversation identity, GitHub schedule reconciliation, no accidental global Master mutation, target `.agent/tasks` retaining exact target bindings, execution-disabled targets remaining non-executable, and emergency controls remaining authoritative. Legacy ADD/REBIND commands may remain for migration compatibility but must not be required for normal donor/target work.\n\n",
)

# Browser/DOM architecture wording.
replace_once(
    "docs/ARCHITECTURE.md",
    "`chat_bridge/service_worker.js` is composition-only. Worker responsibilities are split by ownership: `worker_state.js` serializes Chrome storage, `worker_runtime.js` validates/caches runtime configuration, `worker_binding.js` owns hard-binding lookup and prompt policy, `worker_schedule.js` owns alarms, `worker_transport.js` owns tab/content-script transport and delivery authorization, `worker_controls.js` owns assistant inspection/binding/pacing/maintenance control transitions, `worker_delivery.js` owns one delivery lifecycle, `worker_conversations.js` owns popup/operator conversation/global-setting mutations, `worker_lab_commands.js` owns diagnostic feedback and user-authored `LAB:OP:*` handling, and `worker_events.js` routes Chrome events/messages. `worker_base.js` contains only shared constants and small process-local registries.",
    "`chat_bridge/service_worker.js` is composition-only. Worker responsibilities are split by ownership: `worker_state.js` serializes Chrome storage, `worker_runtime.js` validates/caches runtime configuration, `worker_binding.js` owns transport-workspace lookup plus the minimal chat prompt envelope, `worker_schedule.js` owns alarms, `worker_transport.js` owns tab/content-script transport and delivery authorization, `worker_controls.js` owns assistant inspection/pacing/maintenance plus legacy binding compatibility transitions, `worker_delivery.js` owns one delivery lifecycle, `worker_conversations.js` owns popup/operator conversation/global-setting mutations, `worker_lab_commands.js` owns diagnostic feedback and user-authored legacy `LAB:OP:*` handling, and `worker_events.js` routes Chrome events/messages. `worker_base.js` contains only shared constants and small process-local registries.",
)
replace_once(
    "docs/ARCHITECTURE.md",
    "Content-originated assistant messages may request the explicit exact-id binding mutations `ADD`, `REBIND` and `REMOVE`; user-authored messages have the separate `LAB:OP:*` mutation namespace. Both paths are worker-validated and persistently deduplicated. Assistant controls may alter per-conversation binding/schedule/maintenance state only through their explicit command families and can never mutate the global Master switch.",
    "Legacy content-originated `ADD`/`REBIND` and user-authored `LAB:OP:*` binding commands remain worker-validated and persistently deduplicated for migration compatibility, but they are not normal repository routing. Per-conversation schedule/maintenance controls remain bounded and can never mutate the global Master switch.",
)

# DOM contract: binding revision is retry/compatibility epoch, not repository authority.
replace_once(
    "docs/CHATGPT_DOM_CONTRACT.md",
    "Bridge ownership is derived from the exact current wake/binding envelope. A terminal error following a normal operator-authored prompt may be diagnosed but must not be clicked automatically.",
    "Bridge ownership is derived from the exact current chat wake envelope. Legacy binding revision may remain part of local retry epochs, but repository metadata is not execution authority. A terminal error following a normal operator-authored prompt may be diagnosed but must not be clicked automatically.",
)
replace_regex(
    "docs/CHATGPT_DOM_CONTRACT.md",
    r"## Binding semantics relevant to DOM\n.*?(?=## Intentionally unsupported assumptions)",
    "## Conversation identity relevant to DOM\n\n"
    "One ChatGPT conversation has one concrete Bridge chat identity. Legacy ADD/REBIND metadata may create a new local generation/compatibility epoch, but it does not authorize repository work. Wake ownership and DOM safety are scoped to the exact conversation and current delivery/safety generation.\n\n"
    "A parent Superchat may reason across multiple donor/target repositories without making DOM identity ambiguous. Any Local Agent task still uses the exact canonical binding of its actual target repository.\n\n"
    "Never infer repository execution authority from DOM ids, assistant/user text, renderer structure, Bridge binding metadata or model output.\n\n",
)

# Autonomous loop.
replace_regex(
    "docs/AUTONOMOUS_CHAT_LOOP.md",
    r"This document defines the current autonomous loop.*?explicit release decision\.",
    "This document defines the current autonomous loop connecting a parent Superchat, Chat Bridge 0.8.1 transport, GitHub desired state and deterministic Local Agent execution.",
)
replace_regex(
    "docs/AUTONOMOUS_CHAT_LOOP.md",
    r"## Conversation binding and planner scope\n.*?(?=## Schedule/status control: GitHub only)",
    "## Conversation transport and repository scope\n\n"
    "Every configured conversation has one concrete Bridge chat identity used for wake delivery and scheduling. It is not a repository execution binding.\n\n"
    "The active user goal or durable Conversation Fabric request supplies repository reasoning context and may include multiple donor/target repositories without chat Rebind. Legacy `planner_scope` and binding metadata may remain in runtime state for compatibility/transport-workspace selection, but they are not authorization evidence.\n\n"
    "Every Local Agent task still uses the exact canonical `agent_binding` of its actual **target** repository. An execution-disabled target such as `local-agent` may be inspected/edited through direct GitHub operations but must not receive a Local Agent task.\n\n",
)
replace_regex(
    "docs/AUTONOMOUS_CHAT_LOOP.md",
    r"Example desired state:\n\n```json\n\{.*?\n\}\n```",
    "Example desired state:\n\n```json\n{\n  \"conversation_id\": \"chat-e8ad8275\",\n  \"control_generation\": 4,\n  \"enabled\": false,\n  \"interval_minutes\": 5,\n  \"next_wake_at\": null,\n  \"updated_at\": \"2026-09-30T01:41:54+02:00\"\n}\n```\n\nLegacy repository/binding fields may be accepted in migrated records but are not schedule ownership or repository authorization.",
)
replace_once(
    "docs/AUTONOMOUS_CHAT_LOOP.md",
    "1. identify the conversation binding and authorized planner scope;",
    "1. identify the exact parent conversation and active goal;",
)

# GitHub schedule contract.
replace_regex(
    "docs/GITHUB_BRIDGE_CONTROL.md",
    r"This is the canonical conversation scheduling/control contract.*?out of GitHub\.",
    "This is the canonical conversation scheduling/control contract for Chat Bridge 0.8.1. GitHub desired state owns managed-chat pacing; Bridge remains browser transport and repository authorization remains at executable `.agent/tasks`.",
)
replace_regex(
    "docs/GITHUB_BRIDGE_CONTROL.md",
    r"```json\n\{\n  \"conversation_id\": \"chat-e8ad8275\".*?\n\}\n```\n\nThe worker accepts a control only when.*?locally configured conversation\.",
    "```json\n{\n  \"conversation_id\": \"chat-e8ad8275\",\n  \"control_generation\": 4,\n  \"enabled\": false,\n  \"interval_minutes\": 5,\n  \"next_wake_at\": null,\n  \"updated_at\": \"2026-09-30T01:41:54+02:00\"\n}\n```\n\nThe worker accepts a control when the exact conversation id matches the locally configured conversation and the control payload is valid. Legacy `repository_id`, `repository`, `agent_binding` and `binding_revision` fields may appear in migrated records and are validated when present, but they are not schedule ownership or repository execution authority.",
)
replace_once(
    "docs/GITHUB_BRIDGE_CONTROL.md",
    "`control_generation` is a positive monotonically increasing integer within one binding revision.",
    "`control_generation` is a positive monotonically increasing integer for one managed conversation control stream.",
)
replace_once(
    "docs/GITHUB_BRIDGE_CONTROL.md",
    "Applied GitHub state is tracked by `(bindingRevision, controlGeneration, localGeneration)` plus a canonical signature of the applied desired-state payload.",
    "Applied GitHub state is tracked by chat identity, `controlGeneration`, `localGeneration` and a canonical signature of the applied desired-state payload. Legacy binding revision may remain in compatibility state but is not schedule ownership.",
)
replace_once(
    "docs/GITHUB_BRIDGE_CONTROL.md",
    "- Rebind creates a new binding revision and therefore an independent generation space.",
    "- Legacy Rebind may refresh a compatibility/local-generation epoch, but normal repository routing does not use it.",
)
replace_once(
    "docs/GITHUB_BRIDGE_CONTROL.md",
    "Once a matching GitHub generation has been applied, schedule ownership is sticky for that binding revision.",
    "Once a matching GitHub generation has been applied, schedule ownership is sticky for that managed chat control stream.",
)
replace_once(
    "docs/GITHUB_BRIDGE_CONTROL.md",
    "Malformed controls, duplicate conversation records, stale binding revisions, invalid timestamps/ranges or identity mismatches fail closed.",
    "Malformed controls, duplicate conversation records, stale control generations, invalid timestamps/ranges or conversation identity mismatches fail closed.",
)

# Canonical multirepo guide: rewrite completely.
write(
    "docs/HOST_OPS_MULTIREPO.md",
    """# Superchat multirepo reasoning and Host Ops transport workspace

A parent Superchat may coordinate work across multiple repositories without rebinding the Chat Bridge conversation. `host-ops` remains the canonical execution-enabled operator/transport workspace for Mac-local operations, but its Bridge metadata does not grant repository execution authority.

## Repository scope

Repository scope comes from the active user goal or a durable Conversation Fabric request. It may include donor and target repositories, for example:

```text
parent Superchat
  reasoning context: local-agent + growclip
  donor: local-agent
  execution target: growclip
```

`repository_id` / `repository_ids` are reasoning context only. Legacy `planner_scope`, `repositoryId`, `agentBinding` and binding-revision values may remain in Bridge/runtime state for compatibility or transport-workspace selection; they are not security boundaries and normal work must not use `LAB:REBIND` to switch targets.

## Executable target identity

For every Local Agent task, resolve the actual target repository and use that repository's exact canonical binding:

```text
registry binding == .agent/binding.json binding == task.agent_binding
```

The task never inherits the `host-ops` binding merely because the parent Superchat uses Host Ops for orchestration. Executor validation, repository leases, resource admission, watchdogs, cancellation ownership and durable evidence remain repository-scoped.

## Donor repositories

A donor repository can be inspected, compared or edited through permitted GitHub operations while another repository is the executable target. Donor context never grants machine authority over the target.

The canonical `local-agent` catalog entry is intentionally `execution_enabled: false`; Local Agent source can be inspected or edited through GitHub, but Local Agent must not queue an executable `.agent/tasks` item against its own disabled catalog entry.

## Chat Bridge behavior

A normal wake uses only the stable chat envelope plus the runtime prompt:

```text
[LA_CHAT=<conversation id>]
```

GitHub `conversation_controls` owns pacing for managed chats. Repository/binding fields are not schedule authority. Legacy ADD/REBIND controls remain migration compatibility only.

## Host Ops

Use the execution-enabled `host-ops` repository only for bounded Mac-local operations that genuinely belong to Host Ops: inspecting worktrees/process state, running local release gates, managing isolated development profiles or other host-level operations. Project work belongs to the actual project repository and uses that project's exact task binding.

## Child reasoning

Child chats, when used, are reasoning-only. They may audit, debug, compare donor/target code and propose fixes. They never receive independent machine execution authority; the parent Superchat decides what becomes executable work and queues only exact-bound target tasks.

The current browser child-spawn path has a known `chatgpt_login_timeout` detector failure in the isolated profile. Do not repeat login/Cloudflare/DOM loops as a parent-Superchat acceptance gate. Treat child-browser transport as a separately repairable component while the parent continues operating.

## Security properties

- chat identity is transport/scheduling identity only;
- repository reasoning context does not grant execution authority;
- every executable task uses the target repository's exact canonical binding;
- execution-disabled targets never receive executable tasks;
- global emergency controls, repository leases and task/resource limits remain unchanged;
- GitHub remains the durable control/evidence plane.
""",
)

# Bridge README sections.
replace_regex(
    "chat_bridge/README.md",
    r"## Binding model\n.*?(?=## GitHub-backed pacing/status)",
    "## Transport and repository model\n\n"
    "Every configured conversation stores one concrete conversation id/URL plus local transport/safety state. Legacy repository/binding fields may remain in migrated state for compatibility, but they do not authorize repository work.\n\n"
    "Normal onboarding is repository-agnostic: open the exact ChatGPT conversation and use **Add current chat**. Repository reasoning scope comes from the active goal or durable request and may span donor/target repositories without Rebind.\n\n"
    "Every Local Agent task still carries the exact binding of its **actual target** repository. `local-agent` is intentionally execution-disabled and is edited through direct GitHub operations.\n\n",
)
replace_once(
    "chat_bridge/README.md",
    "Every schedule mutation increments `control_generation`. Status is a read. Binding/repository/revision mismatches fail closed.",
    "Every schedule mutation increments `control_generation`. Status is a read. Schedule ownership is keyed by exact chat identity; legacy binding/repository/revision fields are not schedule authority.",
)
replace_regex(
    "chat_bridge/README.md",
    r"### Binding migration\n.*?(?=### Maintenance/diagnostics)",
    "### Legacy binding migration compatibility\n\n"
    "The parser still recognizes `ADD`/`REBIND`/operator binding commands for old profiles and explicit migration diagnostics. They are not part of normal Superchat repository routing and must not be required to move between donor/target repositories. `REMOVE` remains an explicit conversation-removal control.\n\n",
)
replace_regex(
    "chat_bridge/README.md",
    r"## Wake envelope\n.*?(?=## Wake submission)",
    "## Wake envelope\n\nEvery normal Bridge wake carries the stable conversation identity plus the runtime prompt:\n\n```text\n[LA_CHAT=<conversation id>]\n```\n\nRepository catalog/binding metadata is not injected as execution authority. GitHub-managed pacing remains owned by the exact `conversation_controls` record.\n\n",
)

print("Superchat documentation cleanup applied")
