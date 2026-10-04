# Superchat supervisor

Superchat is the parent reasoning/orchestration layer above Chat Bridge and Conversation Fabric children. It is not an executor and it is not a second scheduler.

```text
Superchat parent
  -> bounded child reasoning
  -> child evidence/results
  -> parent synthesis
  -> target .agent/tasks when execution is justified
  -> deterministic Local Agent executor
```

## Current status

The deterministic foundation is implemented: transport-only chat identity, GitHub-backed controls/evidence, reasoning-only children, isolated child-browser lifecycle, bounded parallel execution, exact target binding and production queue deduplication. The child-browser auth readiness repair is merged.

The next product milestone is not more design work. It is one bounded live acceptance in which a real parent visibly delegates to real child chats on real source code and retains sole execution authority.

## Current documents

- [`../CURRENT_HANDOFF.md`](../CURRENT_HANDOFF.md) — current production/checkpoint state.
- [`../conversation_fabric/CHECKPOINT_2026-10-04_SUPERCHAT_READY.md`](../conversation_fabric/CHECKPOINT_2026-10-04_SUPERCHAT_READY.md) — readiness checkpoint.
- [`../conversation_fabric/CURRENT_PLAN.md`](../conversation_fabric/CURRENT_PLAN.md) — live acceptance sequence.
- [`ROADMAP.md`](ROADMAP.md) — forward roadmap after the self-diagnostic.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — longer-lived architecture boundaries.

Older implementation plans, research logs and evidence captures are historical support material. They do not override the current handoff/plan.

## Product rule

The model decides what should happen. Deterministic infrastructure decides whether and how an external effect is allowed to happen. One parent may coordinate many reasoning workers; machine execution remains target-bound and singular.
