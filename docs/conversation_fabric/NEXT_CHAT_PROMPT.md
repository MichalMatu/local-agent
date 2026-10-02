# Conversation Fabric continuation prompt

Use this prompt to start the next ChatGPT conversation. Repository state, durable documentation and fresh `host-ops` state are authoritative; do not rely on previous chat memory.

---

Continue Conversation Fabric in repository `MichalMatu/local-agent`.

Do not rely on memory from the previous chat. Repository state, durable docs and fresh `host-ops` state are the source of truth.

Read in this order first:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/conversation_fabric/CURRENT_PLAN.md`
4. `docs/DEVELOPMENT_PLAN.md`
5. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

Then fetch and verify fresh mutable state before any effect:

- `main`
- `develop/conversation-fabric`
- `host-ops:agent-control`
- `.agent/status/daemon.json`
- DEV checkout `/Users/michal/local-agent-dev`
- production checkout `/Users/michal/local-agent`

Current production baseline:

- `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent 4.19.12 / Chat Bridge 0.6.2
- production must remain unchanged unless the user makes a separate explicit release decision
- production Chrome profile `/Users/michal/Library/Application Support/Google/Chrome` remains protected

Conversation Fabric accepted development checkpoint:

- canonical branch: `develop/conversation-fabric`
- accepted CODE: `93494b2a99162eef5bcf44caae087b71459233b4`
- commit: `Add end-to-end Conversation Fabric MVP`
- tree: `c4354951c4b4af9c558ce8adc59d2118f51f8146`
- exact-SHA CI: `37076387941`
- all five jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`

Documentation-only commits may advance the canonical branch beyond accepted CODE `93494b2...`. Always distinguish the accepted CODE checkpoint from the current docs head before runtime effects.

The end-to-end DEV MVP is COMPLETE. Do not restart old lifecycle milestones merely to continue backend work.

Accepted bounded lifecycle:

```text
ChildRequest
  -> durable spawn intent
  -> owned ChatGPT child tab
  -> exact bootstrap submit
  -> canonical child identity
  -> ChildRegistration
  -> active
  -> bounded assistant-result observation
  -> durable result evidence
  -> terminal_pending_evidence
  -> terminal_recorded
  -> durable adoption
  -> workflow reasoning node succeeded
  -> retired
  -> close exact owned child tab
```

The accepted MVP also supports a small bounded set of independent child tasks. Browser spawn effects remain serialized; registered children may reason concurrently and the parent may collect results in one campaign.

Important accepted safety/recovery properties:

- no blind resubmit after a potentially submitted effect;
- lost create/submit acknowledgement recovery and restart reconciliation;
- transient provisional-route evidence bound to the exact claimed spawn tab/transaction;
- exact bootstrap-bound identity, including collapsed user turns;
- one bounded observer-session retry after transport stall;
- restart-safe terminal/adoption/retirement ordering;
- first-class fresh manual lifecycle path;
- ambiguous manual attach without resubmit;
- unrecoverable ambiguity abandonment preserves the original ambiguous transaction and never authorizes replacement;
- observer/close ownership is bound to exact transaction/request/bootstrap identity rather than URL alone.

Final clean live acceptance proof:

- workflow: `mvp-clean-final-canary-v1`
- request: `mvp-clean-final-child-001`
- request digest: `sha256:3bfdcf5a72c6f9b8094f74d6d9bb72609d1ce46fb5168cac4b9b1a7473153e91`
- canonical child: `https://chatgpt.com/c/6ac03b3b-cc70-83eb-8f75-09fcbf277733`
- child state: `retired`
- workflow state: `completed`
- terminal record: present
- adoption record: present
- result: `MVP_CLEAN_FINAL_OK` plus exact accepted SHA `93494b2a99162eef5bcf44caae087b71459233b4`
- failures: none
- production mutation: none

The MVP was also used during development to delegate real lifecycle/browser review tasks. Those child reviews found defects; the defects were fixed before the accepted checkpoint. Do not rerun those historical review campaigns.

Current product priority is operator-visible integration / controlled release decision.

Do not begin another abstract lifecycle-hardening milestone. Start with a short read-only product/ownership audit that answers:

- what is the smallest operator-facing entrypoint from the intended long-lived Operator Chat / Superchat into the accepted MVP;
- how bounded child progress/results should be surfaced to the operator;
- which existing `mvp_flow`/conversation APIs can be wrapped directly without duplicating lifecycle state;
- whether a controlled production release should happen now or after one small operator-facing DEV slice;
- what exact version/changelog/release work would be required if release is selected.

Prefer using the accepted MVP itself for a small bounded set of independent reasoning/review tasks when that materially accelerates the next DEV slice. This is not a general fleet scheduler: broad autonomous scheduling, rollover and fleet management remain out of scope.

Use direct GitHub operations for repository-side work and `host-ops` for every Mac-local checkout, synchronization, test, process or browser-profile operation.

Do not touch:

- production `main` without a separate explicit release decision;
- `chat-bridge-state`;
- `operator-control`;
- production Chrome profile `/Users/michal/Library/Application Support/Google/Chrome`.

Do not repeat the Stage 8 campaign or historical MVP acceptance canaries unless runtime code changes require a new proof of the changed external-effect boundary.

First verify fresh canonical/docs head, clean DEV, clean production and fresh daemon state. Then continue autonomously with the smallest operator-visible integration audit/slice. If that slice changes runtime behavior, require focused tests and exact-SHA CI; use live browser proof only when the changed boundary actually requires it.
