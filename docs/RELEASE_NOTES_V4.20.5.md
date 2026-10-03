# Local Agent 4.20.5

## Summary

Local Agent 4.20.5 is the final cleanup patch for the transport-only Superchat rollout. It adds no new execution authority and no scheduler/task-schema change.

Chat Bridge advances to 0.8.1. The parent conversation remains a transport/scheduling channel; repository reasoning scope comes from the active goal and may span donor and target repositories without chat rebinding. Executable work remains fail-closed at `.agent/tasks` with the exact canonical binding of the actual target repository.

## Changes

- Fix `Add current chat` after repository selection was removed from normal onboarding.
- Reduce bootstrap/wake delivery to a minimal `[LA_CHAT=<id>]` envelope plus the GitHub/runtime prompt, avoiding repeated repository catalog and legacy binding policy text in each turn.
- Keep assistant delivery-timeout ownership keyed to the stable chat envelope after that prompt simplification.
- Update Bridge regression tests for the minimal transport envelope.
- Advance Chat Bridge from 0.8.0 to 0.8.1.

## Unchanged safety boundaries

- `.agent/tasks` remains the only executable repository-work contract.
- Every executable task still requires the exact canonical `agent_binding` of its target repository.
- Registry/control/task binding equality, execution-enabled admission, repository identity, leases, resource admission and emergency disable remain unchanged.
- Child chats, when used, remain reasoning-only and receive no independent machine execution authority.
- Legacy Bridge binding/rebind metadata and commands may remain for backward compatibility, but they are not normal repository-routing or authorization boundaries.

## Live evidence before final release

The 4.20.4 parent Superchat rollout proved GitHub-managed wake delivery to the intended parent conversation. A read-only MatrixHub routing proof also confirmed that a transport-only multirepo parent still produced an executable task only under MatrixHub's exact canonical binding and repository checkout, with no edits.

A later child-browser pilot stopped at the known `chatgpt_login_timeout` DOM/login detector path. That optional browser-child path is not a blocker for parent Superchat operation and must not be used to reintroduce repository binding into the chat transport layer.
