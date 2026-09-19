# OpenWorker governance adaptation plan

Status: Phase 0 source audit completed. No runtime behavior changes are authorized by this document.

Base: `main` at `224046066b0df92544337db0ee623e372629e726` (`v4.18.22`).
Candidate branch: `feature/openworker-governance`.
Reference project: `andrewyng/openworker` (MIT), audited at `c79fa9b778867a5a55d28f70c0f6aaa8f11fd7fe`.
Detailed findings: `docs/OPENWORKER_CODE_AUDIT.md`.

## Audit outcome

The source audit recommends a narrow adaptation, not an OpenWorker-style redesign:

1. **P0:** deterministic project-command self-protection floors in the existing task-contract boundary;
2. **P0:** a table-driven Local Agent command-admission security corpus with benign controls;
3. **P1:** compact policy/admission provenance in existing run/result/diagnostic evidence;
4. **P2 only if needed:** exact-digest, pre-claim operator approval using an idempotent durable wait record;
5. **do not adopt:** an embedded LLM reviewer, general desktop permission modes, shell standing grants, connector/provider infrastructure, duplicate audit DB, or durable mid-task shell resume.

The first implementation candidate should therefore remain model-free and preserve ChatGPT as planner and Local Agent as deterministic executor.

## Goal

Evaluate selected governance mechanisms from OpenWorker and adapt only those that materially strengthen Local Agent without moving planning into the executor, weakening hard repository binding, or expanding Local Agent into a general-purpose desktop AI agent.

Local Agent remains a deterministic, bounded execution substrate for ChatGPT. OpenWorker is used as a reference implementation and source of design ideas, not as a new runtime dependency.

## Non-goals

- Do not embed an LLM/model-provider layer in Local Agent.
- Do not add Slack, email, calendar, CRM, MCP-provider aggregation or generic desktop automation.
- Do not replace the Git control plane or Chat Bridge planner boundary.
- Do not weaken immutable task identity, hard agent/repository binding, execution/resource leases, fail-closed emergency controls, bounded watchdogs, checkpointing, durable result publication or self-update rollback.
- Do not add auto-replay of interrupted work.
- Do not copy OpenWorker code mechanically. Prefer native Local Agent designs that preserve existing ownership boundaries and tests. If source is copied directly, preserve the MIT attribution required by its license.

## Existing Local Agent baseline

The audit must start from what Local Agent already guarantees:

- ChatGPT/planner owns intent; Local Agent owns deterministic execution.
- One executable repository has one canonical immutable `agent_binding` UUID.
- Binding mismatches fail closed before command execution.
- Global persistent disable has authority over repository admission.
- Repository-scoped task cancellation exists for exact immutable task ids.
- Claims, results, runs and status are durable/repository-scoped.
- Interrupted claimed tasks are never automatically replayed.
- Command, no-output, whole-task admission and RSS behavior is bounded.
- Process groups and inherited repository/resource leases keep ownership valid through descendants.
- Dirty disposable workspaces are checkpointed before destructive cleanup.
- Publication recovery republishes evidence without rerunning commands.
- Self-update validates before restart and rolls back validation failure.
- Parallel execution has deterministic resource admission and bounded concurrency.

Any OpenWorker-inspired feature must be additive to this baseline rather than a substitute for it.

## Audit targets

### 1. Action policy and hard permission floors

Question: does OpenWorker encode consequential actions in deterministic policy rather than trusting prompt/model judgment?

Local Agent mapping:

- likely owner for immutable execution-policy classification: `local_agent/runtime/task_contract.py` or a new narrowly-owned policy module only if the contract cannot cleanly own it;
- repository/global operation enforcement remains in the existing owners that perform those operations;
- Chat Bridge controls must remain separate from executor authorization.

Candidate improvement:

Introduce explicit action/risk classes only where Local Agent currently relies on task shape or documentation rather than an enforced invariant. Hard floors should be machine-checkable and impossible for planner text to lower.

### 2. Approval provenance

Question: how does OpenWorker record whether an action was user-approved, rule-approved, reviewer-approved or denied?

Local Agent mapping:

- preserve immutable task payload/digest as the execution request;
- add provenance only if it can be represented durably without making the executor depend on ChatGPT conversation state;
- results/runs are preferred evidence surfaces; daemon and worker status should stay compact.

Candidate improvement:

A small normalized authorization/provenance record attached to consequential control actions or task admission may improve auditability. It must be validated, bounded and repository-scoped where applicable.

### 3. Earned/standing authorization rules

Question: does OpenWorker support one-shot approval, standing rules and revocation with deterministic scope?

Local Agent mapping:

Local Agent currently uses explicit immutable tasks, binding and operator controls. A general permission ladder is not automatically desirable. Only consider standing authorization when it removes repeated operator friction without allowing a task to broaden its own authority.

Required properties if adopted:

- rules are explicit data, never inferred from chat history;
- scope is exact (operation, repository/binding, branch/path where relevant);
- expiry/revocation is explicit;
- rules cannot override hard floors or global disable;
- executor cannot create or widen a rule as a side effect of executing a task.

### 4. Circuit breaker / denial escalation

Question: how does OpenWorker stop repeated denied or suspicious actions from turning into an autonomous retry loop?

Local Agent mapping:

Local Agent already has bounded retries, fail-closed operator disable and no automatic task replay. The useful addition would therefore be narrow: detect repeated policy/authorization denials at the correct scope and transition to a durable blocked state rather than repeatedly presenting or attempting equivalent work.

Candidate owner depends on audit findings:

- pure threshold/state classification belongs in a deterministic policy owner;
- durable blocked state belongs with the existing daemon/operator/task evidence owner;
- recovery must be explicit and must not silently requeue old commands.

### 5. Independent verification / checker separation

Question: which OpenWorker operations require a checker distinct from the component that proposed the change?

Local Agent mapping:

Local Agent already separates planner intent from deterministic verification commands. Prefer deterministic independent checks (tests, static analysis, exact diff inspection, policy validation) over adding a second model inside Local Agent.

Candidate improvement:

Strengthen task schemas/workflow policy so high-impact implementation stages can require an independently-defined verification stage whose command/result is separately recorded and cannot be satisfied by merely repeating the implementation command.

### 6. Unattended approval inbox / parked work

Question: how does OpenWorker persist an approval request during unattended work without self-approving it?

Local Agent mapping:

Potentially useful for operations that should wait for explicit operator approval while unrelated repositories continue. It must not convert an already-claimed task into ambiguous replayable state.

Preferred model if needed:

- admission-time parking before claim whenever possible;
- immutable request id/digest;
- explicit approved/denied terminal decision;
- no automatic execution after restart unless the approval record unambiguously authorizes the exact immutable request;
- global disable remains authoritative.

### 7. Audit trail structure

Question: what exact fields does OpenWorker keep for tool calls, policy decisions, approvals and reviewer reasoning?

Local Agent mapping:

Local Agent already retains task/run/result evidence. The audit should identify only missing evidence required to answer:

1. what exact operation was requested;
2. which immutable task/control request caused it;
3. what policy classified it;
4. whether authorization was needed and how it was satisfied;
5. what actually executed;
6. what result/check evidence followed.

Avoid duplicating full command/output data in a second log when existing run/result JSON already owns it.

## Concrete audit method

For each target above:

1. locate the OpenWorker production code and tests, not only README claims;
2. identify the deterministic enforcement boundary;
3. identify persisted state/schema and restart behavior;
4. identify bypass paths and documented hard floors;
5. inspect tests for negative cases;
6. compare with the exact Local Agent owner/invariant;
7. classify the result as `ADOPT`, `ADAPT`, `ALREADY_STRONGER`, or `REJECT`;
8. record proposed files, schema changes, tests, migration/compatibility impact and failure modes.

## Decision criteria

Adopt or adapt only when all are true:

- the mechanism closes a concrete Local Agent gap;
- it can be enforced deterministically outside planner/model text;
- it has one clear code owner;
- it remains bounded and fail-closed;
- it does not introduce automatic replay ambiguity;
- it preserves project-repository isolation and hard binding;
- it can be covered by focused positive and negative tests;
- operational evidence remains understandable after daemon/process interruption.

Reject when any are true:

- the benefit exists mainly because OpenWorker contains its own LLM agent loop;
- Local Agent already provides a stronger invariant;
- implementation would duplicate existing claim/result/operator state;
- the feature requires broad generic-tool permissions inappropriate for Local Agent;
- it weakens deterministic executor boundaries for convenience.

## Expected implementation ownership

No ownership changes are approved yet. The audit should prefer these existing owners:

- task/action validation: `local_agent/runtime/task_contract.py`;
- staged execution/watchdogs: `local_agent/runtime/executor.py`;
- durable execution/result publication: `local_agent/foundation/core.py` and daemon-owned result/claim paths;
- global fail-closed state: `local_agent/operator/local.py`, `local_agent/operator/remote.py`, `local_agent/entrypoint.py`;
- repository task/control admission: `local_agent/repository/worker.py` and `local_agent/supervisor/worker.py`;
- pure scheduling/policy transitions: `local_agent/supervisor/scheduling.py` only when the concern is truly supervisor scheduling;
- diagnostics/inspection: `local_agent/cli/diagnostics.py`;
- planner/Bridge behavior: `docs/AUTONOMOUS_CHAT_LOOP.md` plus the existing `chat_bridge` owners.

Do not create a generic `security.py`, `governance.py` or miscellaneous helper until a stable responsibility cannot fit an existing owner.

## Candidate implementation phases

### Phase 0 - source audit

Completed in `docs/OPENWORKER_CODE_AUDIT.md` against OpenWorker commit `c79fa9b778867a5a55d28f70c0f6aaa8f11fd7fe`. No runtime changes.

### Phase 1 - evidence/provenance only

If the audit finds missing auditability, add the smallest backward-compatible bounded schema extension first. No new automatic authority.

### Phase 2 - deterministic hard floors

Only for operations where the audit proves a real gap. Add negative tests before enabling any new policy path.

### Phase 3 - denial circuit breaker / parked authorization

Only if repeated-denial or unattended-approval behavior is a real operational problem after Phase 1/2. Keep parking pre-claim where possible and require explicit recovery.

### Phase 4 - independent verification contract

Add only if current `steps`/`verify_steps` semantics cannot express the necessary checker separation cleanly. Prefer schema/workflow tightening over a new subsystem.

## Verification requirements for any later runtime change

- focused positive/negative tests for every new policy transition;
- real temporary-Git integration tests when task/control admission semantics change;
- process interruption coverage if durable parked/blocked state is introduced;
- `python scripts/verify.py` on the exact candidate;
- full CI matrix and macOS smoke before any release decision;
- exact `main...candidate` architecture/dependency review;
- downstream documentation audit when task/control/status/planner contracts change;
- explicit release decision before advancing `main`.

## Open questions resolved by the source audit

- OpenWorker hard floors are explicit code paths, but they are also partly distributed between risk classification and tool/permission handling.
- Auto-approve cannot clear `hard_deny` or `human_only` decisions; the reviewer sees only reviewer-eligible asks.
- Reviewer judgment can unlock only the middle `needs_user` class, never a deterministic block.
- The circuit breaker is five consecutive reviewer denials within one user turn; non-deny/user interaction resets it.
- Durable wait records survive restart and are idempotent by session + tool-call identity.
- Unattended sessions do not use the reviewer to self-approve; consequential asks park for a human.
- OpenWorker one-shot "allow anyway" is bound to exact canonical tool arguments and consumed once.
- Standing rules are exact target rules and deliberately exclude shell/local-write authority.
- OpenWorker does not provide complete shell confinement; its own layered security corpus documents unsandboxed-shell gaps.
- For Local Agent, the existing final full verification stage is already a stronger enforceable execution contract than importing OpenWorker persona instructions.

## Audit output

The completed classification, source references, concrete gaps, proposed Local Agent owners, migration impact and test requirements are in `docs/OPENWORKER_CODE_AUDIT.md`.

No runtime implementation should begin by copying OpenWorker. The first candidate should implement only the P0 command self-protection floor + security corpus identified by the audit, then pass Local Agent's normal candidate/release gates.