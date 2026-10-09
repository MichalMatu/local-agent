# No-Bridge Local Agent source-test task plan (draft)

This source-only capability does not depend on Chat Bridge, Chrome tabs,
ChatGPT Send/ACK or hosted GitHub Actions. It supplies a narrow,
deterministic **manual publication candidate** for the already existing
canonical Local Agent task transport.

Function: github_fabric_no_bridge_task_plan.plan_no_bridge_source_test()

## Manual flow

The operator independently confirms the local-agent repository's task binding
and worker readiness, a canonical work/ branch and its exact source SHA.
After explicit operator review opt-in, the pure function returns a frozen
plan containing deterministic task JSON and a canonical task_digest. It
performs **no network I/O** and never submits the JSON to GitHub.

The generated task is intentionally limited to:
- One Mac Python 3.13 verification command, either core or full profile.
- A hard source SHA guard and a clean-checkout guard before any tests.
- allow_write=false, resources=[], pinned agent_binding and work_branch.
- A stable SHA-derived task ID/dedupe key to avoid replaying the same
  submitted plan under a different generated identity.
- Bounded timeout/memory policy and a single command compatible with the
  no-Bridge agent-control result recovery gate.

Any publication is a **separate authorized operator action** and must use
the current canonical agent-control binding, current daemon state, valid
task schema, and the same exact source SHA. A caller may not infer task
publication authorization from a successful local plan validation. There
is no automatic retry, no task execution, no Codex invocation and no
unstated dependency installation. A full test profile may fail because
local dependencies are missing; it must not silently fetch them.

The result path can be checked through PR #245 and a scoped history
through PR #246/#247 after a GitHub task/result commit exists.
Those readers remain redacted, GET-only and default-disabled.

## Non-goals

This is **not** a way to reconstruct or automate a ChatGPT conversation.
The user must manually create/select a separate parent and any real private
conversation source must pass its own authorization. This task planner
cannot retire old/offline Chrome workers or authorize ChatGPT browser effects.
A human passing an opt-in boolean does not constitute authenticated
operator consent; external publication policy remains binding.

## Verification

Tests cover deterministic identity, exact task schema/digest compatibility,
read-only and source-HEAD guard properties, multiple profiles, wrong
bindings/branches/SHAs, malicious task ID strings and forbidden profiles.
Maintain draft status until exact-head Mac tests and independent review.
