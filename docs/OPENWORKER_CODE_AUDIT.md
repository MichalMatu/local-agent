# OpenWorker governance code audit for Local Agent

Status: completed source audit; design recommendations only. No Local Agent runtime behavior is changed by this document.

Local Agent baseline: `MichalMatu/local-agent@224046066b0df92544337db0ee623e372629e726` (`v4.18.22`).
OpenWorker audited baseline: `andrewyng/openworker@c79fa9b778867a5a55d28f70c0f6aaa8f11fd7fe` (current `main` observed 2026-09-19).
Candidate branch: `feature/openworker-governance`.
Companion plan: `docs/OPENWORKER_GOVERNANCE_PLAN.md`.

## Executive conclusion

OpenWorker and Local Agent solve overlapping execution-safety problems from different directions:

- OpenWorker owns its LLM/tool loop and therefore needs a general permission system around arbitrary model-proposed tool calls.
- Local Agent intentionally does not own the model loop. ChatGPT remains the planner and Local Agent accepts immutable, repository-bound execution tasks.

The correct adaptation is therefore **not** to import OpenWorker's permission engine, reviewer model, desktop approval UX, or connector framework. The useful ideas are narrower:

1. add deterministic **executor self-protection floors** for project task commands;
2. improve **authorization/admission provenance** in existing Local Agent evidence rather than create a parallel audit database;
3. use OpenWorker's exact-action/idempotent-state patterns when Local Agent eventually needs an operator approval gate;
4. borrow the **layered security corpus methodology** for Local Agent command/admission policy;
5. keep Local Agent's existing deterministic verification workflow rather than add a second LLM reviewer.

The highest-value first implementation is a small, pure command-admission hardening layer owned by the existing task contract. It should protect Local Agent's own authority/control state and a very small set of unambiguously host-destructive operations. It must not attempt to pretend that static shell parsing is a sandbox.

## Current Local Agent baseline relevant to this audit

Local Agent already has substantial safeguards that should remain authoritative:

- canonical immutable repository/agent binding before execution;
- repository-scoped immutable task digest and durable claim/result identity;
- no automatic replay of interrupted claimed work;
- global persistent fail-closed disable state;
- exact repository task cancellation;
- bounded command/no-output/task/RSS behavior;
- process groups and inherited execution/resource leases;
- checkpointing before destructive disposable-workspace cleanup;
- durable result spool and evidence-only publication recovery;
- validated/rollback-capable self-update;
- bounded parallel scheduling and explicit resources;
- structured work/focused/full verification policy.

The current task contract validates schema, size, bindings, resources, timeouts, and command strings. It also rejects commands containing the local `codex` token. The command executor then launches accepted strings through the normal shell in the repository work directory. This means repository identity is strongly constrained while an accepted shell command still has the OS authority of the Local Agent process.

That distinction is the main target of this audit.

---

## Finding OW-01: intrinsic risk classification is separated from approval policy

### OpenWorker implementation

Files:

- `coworker/risk.py`
- `coworker/permissions.py`
- tests including `tests/test_permissions_risk.py`, `tests/test_mcp_floor.py`, `tests/test_risk_overrides.py`

OpenWorker classifies tools into:

- `READ`
- `EGRESS`
- `WRITE_LOCAL`
- `EXEC`
- `EXTERNAL`

The important part is not the enum itself. It is that a tool's intrinsic floor cannot be lowered by convenient metadata or a user-local override. Built-in write/exec/egress tools, connector writes, and third-party MCP tools have floors. An MCP server declaring `requires_approval: false` cannot turn a third-party action into an unchecked read; at most, later policy may waive one approval card.

`classify()` accepts an override only when it is at least as strict as the established floor. This closes a class of bugs where metadata silently bypasses read-only mode, approval, reviewer, and audit simultaneously.

### Local Agent comparison

Local Agent does not have third-party tool metadata, so copying the risk taxonomy would add abstraction without a corresponding source of risk.

The equivalent boundary is the immutable task contract. The task contract already derives important authority from the task payload rather than trusting free-form planner prose: binding, resources, schema limits, timeouts, task digest, and the local-Codex prohibition.

The gap is that arbitrary accepted shell commands do not have an equivalent deterministic authority floor.

### Decision

`ADAPT` — priority P0.

Do **not** add a generic `RiskClass` subsystem. Add narrowly derived command admission floors for effects that Local Agent itself can identify with high confidence.

### Proposed Local Agent owner

Primary owner: `local_agent/runtime/task_contract.py`.

If the pure command policy grows beyond a small, cohesive set of functions, extract it later to `local_agent/runtime/command_policy.py`; do not create a generic `governance.py` or `security.py`.

### Required properties

- classification is derived from the actual command text/stage, never from a planner-supplied `risk` label;
- the planner cannot lower a hard floor with task metadata;
- hard-floor validation runs before task claim/execution;
- failures are terminal task-contract failures and execute no task command;
- the policy is pure/deterministic and testable without Git/process side effects;
- known bypass limitations are documented honestly.

---

## Finding OW-02: self-protection floors execute before every bypass/allow path

### OpenWorker implementation

File: `coworker/permissions.py`.

`PermissionEngine.evaluate()` deliberately orders policy this way:

1. self-protection floor;
2. read-only mode restrictions;
3. write-root scoping;
4. persistent-authority / deferred-execution human floors;
5. only then bypass/allowlists/session grants/reviewer paths.

Protected OpenWorker state includes configuration, trust/risk overrides, unattended settings, the session database, secrets, and routing state. A normal tool call cannot modify those surfaces even when the user selected a broad bypass mode. OpenWorker also reserves project files that execute later — Git hooks, CI configuration, VS Code tasks, `.coworker/` — for direct human attention.

This is a good architectural property: the mechanism that grants ordinary work cannot rewrite the mechanism that decides what ordinary work may do.

### Local Agent comparison

Local Agent already protects its control authority structurally in several places:

- global disable is a dedicated persistent operator state;
- remote enable cannot clear the local disable marker;
- workers cannot directly service global daemon restart/self-update;
- the `local-agent` catalog binding is non-executable infrastructure;
- source update has installation locking, validation and rollback.

However, a project task's shell command is still an arbitrary user-level shell. Repository binding changes the cwd/identity but is not an OS sandbox. In principle, an admitted project command can name Local Agent's own state paths or invoke its operator CLI directly.

The most important protected surfaces are currently under:

- the installed Local Agent checkout (`local_agent.paths.repository_root()`);
- `~/Library/Application Support/local-agent/`, including `disabled.json`, `repositories.json`, claims/runs/result-spool and installation state;
- repository control/checkpoint infrastructure under the registry's configured paths;
- Local Agent service/operator commands that can clear or rewrite authority.

### Decision

`ADAPT` — priority P0, but much narrower than OpenWorker.

### Proposed first hard floors

Project execution tasks should be rejected before claim when a command unambiguously attempts to:

1. invoke Local Agent's operator mutation CLI (`enable`, `reset-runtime`, `migrate-bindings`) or equivalent known launchers/control entrypoints;
2. directly write/delete/move the persistent Local Agent state directory or installed runtime checkout;
3. directly mutate another repository's Local Agent control/checkpoint infrastructure;
4. directly manipulate Local Agent launchd/service lifecycle from a project task;
5. perform a tiny set of unmistakable host-destructive operations such as root filesystem/disk wipe patterns, if the match can be made with very low false-positive risk.

`disable` deserves special treatment: blocking a project task from invoking it is reasonable, but the independent emergency operator path must remain available. The hard floor is about project-task authority, not removal of the operator control.

### Important limitation

Text matching is defense in depth, not containment. A shell can encode effects in scripts, interpreters, substitutions, or indirect binaries. OpenWorker's own source explicitly acknowledges the same limitation for shell self-protection, and its security corpus documents unsandboxed shell execution as a known gap.

Therefore this phase must not claim that arbitrary shell commands are workspace-confined. A real guarantee would require an OS sandbox/capability boundary, which is a separate design project.

---

## Finding OW-03: OpenWorker's shell allowlist parser is useful as a negative design reference

### OpenWorker implementation

File: `coworker/permissions.py`.

For prefix allowlists OpenWorker refuses auto-allow when a command contains opaque constructs such as substitutions/redirections/variable expansion; splits compound commands; checks every component independently; and refuses nested executors/interpreters/dangerous flags such as `xargs`, `sh -c`, `find -exec`, `-delete`, `sudo`, `ssh`, containers, package runners, and inline interpreter code.

This is careful and testable, but it solves a specific OpenWorker problem: determining whether a command may skip an approval card.

### Local Agent comparison

Local Agent does not need a general shell allowlist. Every accepted task is already an explicit immutable planner-produced request bound to one repository, and adding a command-prefix allowlist would cause heavy maintenance and likely break legitimate build/test/tooling work.

### Decision

`REJECT` as a general feature.

Reuse only individual parsing principles if required by a narrow hard floor:

- fail closed on malformed parsing;
- do not treat prefix matching as semantic containment;
- do not let a harmless prefix bless nested execution;
- test compound/quoted/indirect variants.

---

## Finding OW-04: persistent authority is treated differently from ordinary mutation

### OpenWorker implementation

File: `coworker/permissions.py`.

`PERSISTENT_AUTHORITY_TOOLS` includes saved skills and create/update/delete scheduled tasks. These calls are classified as consequential by name even if metadata is wrong and always require a human because their authority outlives the current session.

The standing-approval tests also prevent the agent from minting broad permission changes through the normal update path.

### Local Agent comparison

Local Agent already embodies the same principle more strongly in its architecture:

- an executable repository has immutable binding identity;
- binding changes are explicit operator actions;
- project workers cannot perform global daemon maintenance;
- self-update is a separately validated control operation;
- global remote enable does not remove local disable state;
- the infrastructure repository binding is not executable.

### Decision

`ALREADY_STRONGER` for existing persistent Local Agent authority.

Add P0 tests only where OW-02 hard floors reveal a shell path that can sidestep these structural boundaries. Do not add another persistent-authority subsystem.

---

## Finding OW-05: exact-action one-shot authorization is substantially safer than category approval

### OpenWorker implementation

Files:

- `coworker/engine.py`
- `tests/test_auto_approve.py`

When the reviewer denies an action and the human chooses "Allow anyway", the grant is keyed to the exact tool plus canonical arguments. It is consumed on the first matching action. An identical second proposal is not covered, and any argument difference returns to normal review.

This avoids a common approval bug: "I approved one shell action" accidentally becoming "shell is approved".

### Local Agent comparison

Local Agent's task digest already gives an even better primitive for task-level identity: SHA-256 over canonical immutable task JSON. Claims/results/status already carry that digest.

If Local Agent ever introduces approval-gated admission, the approval should bind to:

- exact repository id;
- exact canonical `agent_binding`;
- exact `task_id`;
- exact `task_digest`;
- approval request id;
- explicit decision and resolver;
- optional expiration/revocation metadata.

An approval for one digest must never authorize a changed payload with the same task id.

### Decision

`ADOPT THE PATTERN`, not the implementation — priority P1 only when an approval gate is actually introduced.

Do not add approval UI/state merely because OpenWorker has it. Local Agent's present workflow intentionally optimizes for uninterrupted ChatGPT-driven execution.

---

## Finding OW-06: standing approvals are deliberately exact-target and exclude shell/local writes

### OpenWorker implementation

Files:

- `coworker/permissions.py`
- `tests/test_standing_approvals.py`

Standing rules are `tool -> exact target`, scoped to an automation/task. Eligibility is intentionally restricted to external-risk tools with a declared target. `run_shell` is never eligible. Local file writes are never eligible. GitHub thread rules include exact owner/repo/number identity. Read-only modes still override standing rules.

Tests also ensure a scheduled task's user-approved rule can persist while the normal agent update path cannot mint arbitrary new permission entries.

### Local Agent comparison

This mechanism is designed for repeated connector actions such as posting to the same Slack/GitHub target. Local Agent's useful work is predominantly repository-local shell/build/test execution. Importing a standing command rule system would broaden authority for the exact category OpenWorker intentionally excludes.

### Decision

`REJECT` for shell/task execution.

If Local Agent later gains a small set of non-shell external actions, reconsider exact-target rules for those actions only.

---

## Finding OW-07: the reviewer model is structurally subordinate to deterministic policy

### OpenWorker implementation

Files:

- `coworker/reviewer.py`
- `coworker/engine.py`
- `tests/test_auto_approve.py`

The second-model reviewer has good containment rules:

- it can convert only `needs_user` into allow;
- hard denies and `human_only` decisions never reach it;
- exactly one action is reviewed per request;
- malformed/empty/error/timeout output becomes `unsure`, which reaches a human;
- untrusted page/mail/file contents are excluded from reviewer context;
- the reviewer gets user words, a bounded known-world description and the exact proposed action;
- detailed denial reasons are shown to the user but not returned to the acting agent;
- unattended sessions never use the reviewer.

The code and tests are unusually explicit about the distinction between model judgment and policy.

### Local Agent comparison

Adding this subsystem would conflict with Local Agent's most valuable architectural property: ChatGPT is the high-capability planner, while Local Agent is model-free deterministic execution infrastructure. It would also introduce an API/provider dependency and cost into the executor.

### Decision

`REJECT` — priority N/A.

Do not add a second LLM reviewer to Local Agent.

What **is** worth copying is the dependency direction:

> probabilistic judgment may narrow interruptions, but it must never relax a deterministic hard floor.

For Local Agent, that means any future ChatGPT-side recommendation/approval metadata remains subordinate to executor-side binding, operator disable, task-contract and hard-floor validation.

---

## Finding OW-08: reviewer circuit breaker is good locally, but solves a problem Local Agent does not currently have

### OpenWorker implementation

Files:

- `coworker/engine.py`
- `tests/test_auto_approve.py`

The breaker threshold is five **consecutive** reviewer denials in one user turn. After the fifth denial the reviewer is paused for the rest of the turn and subsequent approval requests route to the human. `allow`, `unsure`, or an explicit user answer resets the streak. The pause is visible and persisted as a notice.

This prevents an LLM-agent/reviewer pair from entering a repeated reject/re-propose loop while preserving usability in long turns.

### Local Agent comparison

Local Agent has no embedded action reviewer and does not automatically replay failed/interrupted tasks. Scheduler retries are already bounded and separated from task re-execution. Therefore the exact OpenWorker breaker is not applicable.

A future approval-gated admission queue might need a different breaker: repeated denied **task digests or equivalent policy violations** from the same repository/conversation should stop auto-queuing and require explicit operator action.

### Decision

`REJECT NOW`; `ADAPT LATER` only if a real repeated-approval loop appears.

Do not add unused state machinery in anticipation of a problem that Local Agent's current architecture avoids.

---

## Finding OW-09: durable wait queue has excellent idempotency semantics but cannot be copied mid-task

### OpenWorker implementation

File: `coworker/inbox.py`.

The class currently named `InboxStore` is explicitly documented as a durable wait queue. Its state machine is:

`pending -> resolved`

with:

- exactly-once resolution;
- first-responder-wins semantics;
- durable persistence;
- idempotency by `(session_id, tool_call_id)`;
- resolver identity and timestamps;
- reconnect/restart reconciliation;
- one authoritative record regardless of the surface used to answer.

An agent can park on a tool approval, restart/reconnect, recover the same item, and continue once it has a durable decision.

### Local Agent comparison

Copying this literally would violate a core Local Agent invariant if used after task claim: interrupted claimed work is never automatically replayed. Resuming a suspended arbitrary shell sequence after daemon/process loss creates exactly the ambiguity Local Agent avoids.

The safe Local Agent adaptation is **pre-claim admission parking only**:

1. immutable task exists remotely;
2. deterministic admission classifies it as requiring operator authorization;
3. Local Agent creates/reuses a durable approval record keyed to repository/binding/task digest;
4. task remains unclaimed and executes no command;
5. approval is resolved exactly once;
6. a later fresh admission pass verifies the same exact digest and then claims normally;
7. process loss after claim still follows the existing no-replay rule.

### Decision

`ADAPT` — P1/P2 only if approval-gated task classes are introduced.

This is the correct place to borrow OpenWorker's idempotent wait-state pattern without weakening Local Agent's recovery semantics.

---

## Finding OW-10: audit provenance is strong, but a second Local Agent audit database would duplicate evidence

### OpenWorker implementation

File: `coworker/audit.py`.

OpenWorker has a durable SQLite event log containing fields such as:

- session / agent / workspace;
- connector / tool;
- stage / status;
- approval and reason;
- sanitized arguments;
- result preview / resource;
- call id;
- actor / approved_by;
- reviewer token/caching metrics.

`call_id` joins proposed/reviewer/approval/result stages for one action. Sensitive argument keys and message bodies are redacted/truncated before persistence. Reviewer statistics are reconstructed from durable rows.

### Local Agent comparison

Local Agent already persists stronger execution identity than a general desktop-agent tool log:

- repository identity;
- immutable `task_digest`;
- attempt/claim identity;
- command/stage results;
- status/progress/results;
- daemon version and timing/failure evidence.

A new SQLite audit stream would create two competing sources of truth for task execution.

The genuine gap is narrower: Local Agent evidence does not yet need to explain an authorization decision because there is no approval layer. If P0 hard floors/P1 approvals are added, result/admission evidence should include a compact normalized policy record.

### Decision

`ADAPT` — P1, using existing evidence surfaces.

### Proposed evidence shape

For rejected or approval-gated admission, record bounded fields such as:

```json
{
  "policy": {
    "version": 1,
    "decision": "deny",
    "rule": "protected_local_agent_state",
    "task_digest": "...",
    "repository_id": "...",
    "agent_binding": "..."
  }
}
```

If explicit approval is later added:

```json
{
  "authorization": {
    "request_id": "...",
    "decision": "approved",
    "approved_by": "operator",
    "approved_at": "...",
    "task_digest": "..."
  }
}
```

Do not duplicate full command output or the complete task payload in another store.

---

## Finding OW-11: audit redaction is worth applying to any new policy evidence

### OpenWorker implementation

`coworker/audit.py` redacts token/secret/password/API-key fields, browser typed text, message bodies/content/html and bounds nested/list/string values.

### Local Agent comparison

Current run/result evidence intentionally contains executable command/output evidence and therefore has different retention semantics. A future approval/policy surface, however, should not create additional copies of potentially sensitive command bodies just to explain a policy decision.

### Decision

`ADOPT THE PRINCIPLE` — P1.

Store stable rule identifiers and digests where possible. If a short command preview is necessary for diagnostics, bound/redact it independently from the canonical run/result evidence.

---

## Finding OW-12: OpenWorker's deterministic/security test corpus is one of the best ideas to transfer

### OpenWorker implementation

Files:

- `tests/corpora/LAYERED_CORPORA.md`
- `scripts/build_layered_corpora.py`
- `scripts/validate_layered_corpora.py`
- `tests/test_layered_corpora.py`

OpenWorker deliberately separates three questions:

1. deterministic permission-gate outcome;
2. one-action reviewer judgment;
3. multi-action/provenance effects.

The current corpus has 314 scenarios. Importantly, it stores both `expected_current` and `expected_secure`. A known vulnerability is not silently blessed as a regression expectation; differences must carry `known_gap` and `failure_point`.

The corpus also contains matched benign controls and holdouts, so tightening policy can be measured for false positives instead of only adding scary examples.

### Local Agent comparison

Local Agent has strong focused tests, real temporary-Git integration tests, process-lifecycle tests, parallel overlap/resource tests and full release verification. What it does not have is a compact table-driven security corpus for command-admission decisions.

That would be especially valuable for P0 because shell-policy changes otherwise tend to become an ad-hoc list of regex regressions.

### Decision

`ADOPT` — priority P0 alongside the first command hard floor.

### Proposed Local Agent corpus

Create a deterministic corpus under e.g.:

`tests/corpora/command_admission.jsonl`

with fields:

```json
{
  "id": "...",
  "command": "...",
  "expected": "allow",
  "secure": "allow",
  "rule": null,
  "tags": ["benign", "git"],
  "why": "..."
}
```

Outcomes should stay small:

- `allow`
- `hard_deny`

Do not invent `reviewer_eligible` until Local Agent actually has an approval layer.

Initial case families:

- normal PlatformIO/Python/Node/Git build/test/status/diff commands;
- project-local cleanup (`rm -rf build`, generated files);
- multiline shell used by current planner tasks;
- commands naming Local Agent state/checkout/control paths;
- operator `enable/reset-runtime/migrate-bindings` attempts;
- launchd/service-control attempts aimed at Local Agent;
- direct cross-repository control/checkpoint mutation;
- root/disk destructive commands;
- interpreter/nested-command variants for every protected rule;
- benign controls containing similar words/filenames so false positives are visible.

Use explicit current-vs-secure fields only when a known gap cannot yet be fixed. Never silently set the insecure current behavior as the desired assertion.

---

## Finding OW-13: OpenWorker's own security corpus proves its permission engine is not a shell sandbox

### OpenWorker implementation

`scripts/build_layered_corpora.py` explicitly marks shell cases where current production routes a command to the reviewer but recommended security is `human_only` or `hard_deny`.

The recorded failure point is effectively:

> the LocalExecutor is unsandboxed and the deterministic gate does not parse shell effects.

Examples include:

- writes outside the workspace through shell redirection;
- credential reads;
- environment dumping/exfiltration;
- indirect mutation of OpenWorker state;
- persistence and privilege escalation;
- disk/root deletion;
- download-and-execute;
- package lifecycle hooks;
- force push to main.

It also records deferred-execution file surfaces missing from the current protected-path list, including package/build hooks and environment/devcontainer/git configuration.

### Local Agent comparison

This is critical when borrowing ideas: copying OpenWorker's current permission code would not create real shell containment in Local Agent. It would import both complexity and known limitations.

### Decision

`REJECT COPY`; use the corpus as a threat-model input.

Local Agent documentation for P0 must explicitly state:

- hard floors protect named Local Agent authority surfaces and obvious catastrophic cases;
- arbitrary accepted repository commands remain full user-level commands;
- strong shell containment, if ever required, needs an OS isolation design.

---

## Finding OW-14: unattended reviewer behavior is safer than auto-approval, but Local Agent's no-replay model is stronger for execution recovery

### OpenWorker implementation

OpenWorker never lets the reviewer auto-approve unattended sessions. Consequential actions park for a human in the durable wait queue. The item survives reconnect/restart and can be answered from another surface.

### Local Agent comparison

Local Agent already avoids the most dangerous unattended recovery ambiguity: a claimed task interrupted by daemon/process failure is not silently replayed. It also separates project work from global emergency/operator control.

The missing capability is convenience, not correctness: there is no generic pre-claim human approval inbox because Local Agent currently does not require one for normal repository tasks.

### Decision

`ALREADY STRONGER` on no-replay correctness; `ADAPT LATER` only for optional pre-claim approval UX.

---

## Finding OW-15: checker separation in OpenWorker is partly process guidance, while Local Agent already has an enforceable verification shape

### OpenWorker implementation

Security persona/skill guidance instructs the agent to:

- run deterministic scanners;
- fix findings;
- add tests;
- re-scan/review diffs;
- keep PRs focused;
- never merge its own security PR.

This is valuable workflow design, but much of it is instruction-level rather than an engine-enforced separate checker identity.

### Local Agent comparison

Local Agent already has an executable verification contract. `efficient-verification-v1` requires structured stages, disallows legacy command fields, distinguishes `work` / `focused` / `full`, requires exactly one `full` verification stage, and requires that full stage to be final.

This is more directly enforceable than a persona instruction saying "re-scan after fixing".

The planner can still choose both work and verification commands, so it is not cryptographically independent. But adding a second LLM or verifier process is not justified by the evidence reviewed here.

### Decision

`ALREADY STRONGER` for deterministic execution verification.

No new runtime subsystem now. If a future incident shows a real false-verification failure mode, extend the existing workflow policy with one narrow invariant instead of importing OpenWorker's persona architecture.

---

## Finding OW-16: denial details withheld from the acting model is a useful anti-adaptation principle

### OpenWorker implementation

When the reviewer denies an action, the human gets the full reviewer reason, while the acting agent receives a deliberately terse message telling it not to retry/variant-bypass. This prevents the safety component from becoming an oracle that teaches an injected agent how to evade the next check.

### Local Agent comparison

Local Agent has no in-process model to hide diagnostics from. ChatGPT is also the planner/operator-facing intelligence and needs actionable execution evidence.

### Decision

`REJECT` as-is.

If Local Agent later gains a separate untrusted autonomous sub-agent, re-evaluate. Do not degrade current planner diagnostics now.

---

# Prioritized implementation proposal

## P0-A — deterministic Local Agent self-protection floors

Goal: prevent project task payloads from directly rewriting the Local Agent authority that admits/controls those payloads.

Initial implementation scope:

1. add a pure command-policy helper in/under `local_agent/runtime/task_contract.py`;
2. run it for `commands`, `verify_commands`, structured `steps` and `verify_steps` during `validate_task()`;
3. reject unambiguous direct attempts against protected Local Agent control/state/service surfaces;
4. keep rejection pre-claim and terminal;
5. emit a stable rule id in diagnostics/result rejection evidence where the existing rejection path permits it;
6. add a table-driven corpus and focused negative/benign-control tests.

Do not attempt generic shell confinement in this phase.

### Candidate rule families

Exact rule names should be finalized during implementation, but a sensible first set is:

- `local_agent_operator_mutation`
- `local_agent_state_mutation`
- `local_agent_installation_mutation`
- `local_agent_service_mutation`
- `cross_repository_control_mutation`
- `catastrophic_host_destructive_command`

The implementation must be conservative enough that every rule has strong benign controls.

### Tests required

- every command field shape (`commands`, `verify_commands`, `steps`, `verify_steps`);
- multiline commands;
- quoting/absolute/`~` path spellings;
- interpreter wrappers where the dangerous target remains statically visible;
- direct operator CLI attempts;
- project-local commands with similar words that must remain allowed;
- current normal build/test commands from downstream repositories;
- validation proves no command starts on rejection.

## P0-B — command-admission security corpus

Land with P0-A, not later.

A policy without a benign/dangerous corpus will become regex folklore. The corpus is what makes future tightening reviewable.

Keep it deterministic and model-free.

## P1 — normalized policy provenance in existing result/diagnostic evidence

Once P0 has stable rule ids, expose the rule that rejected a task without copying full sensitive payloads into a second database.

Candidate fields:

- policy version;
- decision;
- rule id;
- task digest;
- repository id/binding;
- bounded diagnostic message.

Preserve current terminal task-contract semantics.

## P2 — optional pre-claim operator approval gate

Implement only when a concrete use case exists, for example a future host-maintenance task class that should not run merely because ChatGPT queued it.

Use OpenWorker's durable wait-state principles but Local Agent semantics:

- exact digest binding;
- pending/resolved exactly once;
- first responder wins;
- pre-claim only;
- no resume/replay of claimed commands;
- global disable overrides approval;
- explicit operator identity where available.

Do not make ordinary repository coding tasks approval-heavy.

## P3 — only if demanded by threat model: real OS command isolation

Static command policy cannot provide workspace confinement. If Local Agent eventually needs that guarantee, evaluate a real macOS execution sandbox/container/capability model separately.

This is intentionally **not** bundled with the OpenWorker adaptation branch until requirements and compatibility are clear.

---

# Features explicitly not recommended

Do not import these from OpenWorker into Local Agent now:

- LLM reviewer / Auto-Approve model calls;
- provider/model routing;
- connector risk catalog;
- generic desktop permission modes;
- shell prefix allowlists as the primary trust mechanism;
- session/domain/tool standing grants;
- Slack/email/calendar/CRM inbox routing;
- duplicate SQLite execution audit database;
- durable mid-task shell resumption;
- OpenWorker persona/skill system as a security boundary.

They add complexity without addressing Local Agent's actual architecture.

---

# Proposed file-level change map

No code is changed yet. For the first implementation candidate:

| Local Agent file | Proposed responsibility | Change type |
| --- | --- | --- |
| `local_agent/runtime/task_contract.py` | pure protected-command admission and stable rule ids | runtime, P0 |
| `tests/test_runtime_task_contract_module.py` | direct policy unit coverage | tests, P0 |
| `tests/corpora/command_admission.jsonl` | benign/dangerous current-vs-secure cases | tests/data, P0 |
| `tests/test_command_admission_corpus.py` | corpus execution/validation | tests, P0 |
| `local_agent/cli/diagnostics.py` | expose policy rejection details if needed | runtime/diagnostics, P1 |
| existing worker rejection paths | preserve stable policy evidence on terminal pre-claim reject | runtime, P1 |
| `docs/ARCHITECTURE.md` | document command-admission boundary and non-sandbox limitation | docs, P0/P1 |
| `docs/GOLDEN_STANDARD.md` | add released invariant only after implementation/release | docs, release |
| release notes / changelog | normal behavior-changing release metadata | docs, release |

Avoid changes to `runtime/executor.py` in P0 unless enforcement cannot be guaranteed pre-claim. The preferred architecture is to reject before `spawn_shell()` is reachable.

---

# Release/verification consequences

P0 changes task admission semantics, so it is behavior-changing and must follow the repository's normal candidate/release policy:

1. focused task-contract positive/negative tests;
2. corpus tests with benign controls;
3. worker-level evidence that rejected commands execute nothing;
4. exact candidate architecture/dependency review;
5. `python scripts/verify.py`;
6. full CI matrix;
7. macOS ARM64 smoke on the exact final SHA;
8. downstream planner-documentation audit because accepted task-command semantics change;
9. release version + release notes + changelog;
10. explicit release decision before advancing `main`.

The branch must remain non-production until those gates pass.

---

# Final recommendation

The OpenWorker review does **not** justify rebuilding Local Agent into OpenWorker.

It validates the existing Local Agent direction: keep intelligence in ChatGPT and keep the local executor deterministic, bounded and recoverable.

The concrete improvement worth implementing is much smaller and stronger:

> Add deterministic task-command self-protection floors, backed by a security corpus, so a project task cannot directly rewrite the Local Agent authority that executes project tasks.

After that, add compact policy provenance to existing evidence. Only introduce a durable approval queue if a real workflow later requires it.

That sequence gives Local Agent the best transferable part of OpenWorker's governance model without sacrificing the architecture, throughput or cost model that make Local Agent useful.