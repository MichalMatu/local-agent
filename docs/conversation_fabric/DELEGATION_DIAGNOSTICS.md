# Conversation Fabric delegation diagnostics

The existing **Fabric** row in the Chat Bridge popup reports the last
machine-observed control admission event (in its text when no campaign exists, or its tooltip for an active campaign) for the current managed chat. It never
sends a user message or changes campaign scheduling, spawn, recovery, or terminal
feedback.

| Event | Meaning |
| --- | --- |
| `control_rejected` | Content parsing or completion guard rejected the visible control before worker admission |
| `control_worker_rejected` | Worker received the control but rejected admission, ownership, or capacity |
| `control_accepted` | Worker acknowledged the control; inspect the existing Fabric campaign and feedback fields next |
| `control_transport_failed` | Content-to-worker transport failed before acknowledgement |

The record is diagnostic, **not proof of child creation or result capture**.
An accepted control can still lead to failed, ambiguous or pending children.

## Safe diagnosis without replay

1. Open the exact managed parent tab and Chat Bridge popup.
2. Check Master, current parent enabled state, **Fabric** intake diagnostic,
   **Fabric** campaign state, result counts, pending/ambiguous/failed child IDs,
   and **Feedback** status.
3. If intake is absent, inspect the Chrome extension service-worker and parent
   content-script console for rejected/missing control and injection errors.
   Do not assume that delegation reached the worker.
4. If intake was rejected, resolve the parser/admission reason before any new
   explicit delegation. If the worker accepted it, use the current campaign
   evidence to distinguish spawn, observation, and terminal delivery failures.
5. Do not automatically replay child bootstraps or create replacement tabs.
   An explicit inspect control is read-only; an explicit retire is a separate
   operator decision.

The `bridgeConversationFabricDiagnosticsV1` storage record retains at most
128 managed-chat entries. Each contains only an event enum, bounded reason
code, and observation timestamp. Raw controls, prompts, child bootstrap text,
repository authority, and message bodies are not stored. Only an authorized,
top-frame message from the exact managed parent can update a record.

The diagnostics are an additive debugging tool. Existing production
Conversation Fabric state, journals, result vault and at-most-once worker
delivery remain authoritative. Never use these diagnostic records as control
or execution evidence.
