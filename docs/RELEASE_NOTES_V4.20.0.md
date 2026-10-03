# Local Agent 4.20.0

## Summary

Local Agent 4.20.0 is the first release candidate that carries the accepted Conversation Fabric operator path on top of the 4.19.12 production network-resilience baseline. Chat Bridge advances to 0.7.0 to provide the bounded child-chat spawn/observation actuator required by Conversation Fabric.

## Conversation Fabric

- The existing accepted lifecycle covers durable spawn intent, exact bootstrap submission, canonical child identity, registration, bounded result observation, durable terminal evidence, adoption, retirement and exact owned-tab cleanup.
- Bounded multi-child campaigns reuse that lifecycle; browser spawn effects remain serialized while registered children may reason concurrently.
- Operator Chat / Superchat intent is represented separately from executable repository work under `.agent/conversation/requests/<request-id>.json`.
- Bounded immutable operator results are published under `.agent/conversation/results/<request-id>.json`.
- `.agent/tasks` remains the executable repository-work contract and is not overloaded with reasoning-child lifecycle state.
- Conversation Fabric does not use MCP, Native Messaging or a second scheduler/control transport. GitHub remains the durable control/evidence plane.

## Reliability and recovery

- Long browser campaigns execute outside repository/resource leases; only bounded control staging/publication runs under control synchronization.
- Requests are bound by canonical digests and same-id payload conflicts fail closed.
- Terminal results are locally spooled before publication and survive restart.
- Publication revalidates the exact request identity after synchronization and requires fresh fetched-origin proof of both request and result before deleting the local spool.
- Global disable suspends/recoverably interrupts the campaign path instead of fabricating terminal reasoning failure, and one-shot supervisor operation does not exit while a terminal operator result still needs publication.
- The merged release preserves the 4.19.12 Git transport policy: a 20-second per-attempt cap, one transient retry after two seconds and the process-local control Git circuit breaker.

## Chat Bridge 0.7.0

- Adds the bounded Conversation Fabric spawn/staging actuator and exact child-route/ownership support used by the accepted lifecycle.
- Existing managed-conversation pacing remains GitHub-backed.
- Runtime schema remains 3.
- Content protocol remains v13.
- Assistant guard remains v8.
- Production Chrome/profile state is not changed merely by installing source code; rollout remains explicit.

## Compatibility and rollout

- Task schema, hard binding, repository resources and normal project task admission remain unchanged.
- The new operator intake is default-disabled and requires explicit Conversation Fabric runtime path configuration before the supervisor will start campaigns.
- Production remains Local Agent 4.19.12 / Chat Bridge 0.6.2 until an explicit release decision advances `main`, tags `v4.20.0`, updates/reloads the unpacked Bridge and validates the installed runtime.
- Downstream planner documentation does not require task-construction changes because executable `.agent/tasks` fields and binding/resource semantics are unchanged. The new operator namespace is Local Agent/Superchat control-plane functionality and is documented in the canonical Local Agent operations and Conversation Fabric documents.

## Release-decision evidence

- The exact-RC live proof was attempted in the isolated DEV profile and failed closed before child creation because the profile required ChatGPT login (`chatgpt_login_timeout`). No production Chrome/profile was mutated, and the attempt is intentionally not repeated.
- The accepted operator-visible CODE `37e480d3b36a5c15db89c944ef46f01225a4b379` has a clean live operator proof; the accepted browser/operator lifecycle files are byte-identical to the corresponding RC files, and the RC passed exact-SHA CI.
- On 2026-10-03 the user explicitly approved a controlled production rollout with Conversation Fabric operator intake remaining disabled. This documented release decision accepts the existing lifecycle evidence and closes the external-login proof loop; it is not a claim that the blocked exact-RC child was created.

## Required release gates

Before `main` may advance, the exact final candidate must pass focused Conversation Fabric and 4.19.12 network-resilience regression tests, repository-wide verification, Python compatibility/coverage, macOS smoke and Bridge browser CI. The operator boundary must additionally have either a production-shaped request/result proof confirming the default-disabled/explicit-enable boundary and child lifecycle without mutating production Chrome, or a documented release-decision exception grounded in accepted live evidence and byte-identical external-effect files; this RC uses the latter.
