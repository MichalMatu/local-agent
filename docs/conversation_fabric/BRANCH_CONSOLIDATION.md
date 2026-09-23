# Branch consolidation record

Canonical development branch: `develop/conversation-fabric`.

Production/runtime branches remain separate: `main`, `chat-bridge-state`, `operator-control`.

## Completed transplants

- Latest transient-assistant recovery line is inherited directly by the canonical branch. The former `work/chat-bridge-live-chat-states`, `maintenance/transient-recovery-patch`, and `work/transient-recovery-validation` branches have zero commits ahead of the canonical branch.
- Execution Fabric verified core is active under `local_agent/workflow/`, with workflow CLI, shared control-Git lock, fixtures, disposable-Git integrations, and the complete workflow regression corpus transplanted from the verified donor baseline.
- Event substrate active code includes the durable result outbox, notification-only Chrome Native Messaging host/installer tests, and the pure persisted event-wake state model with tests.
- Conversation Fabric design/re-audit/implementation/source-map/handoff documents are copied into the canonical branch.
- The consolidated development roadmap is copied into the canonical branch.

## Exact donor snapshots

Four diverged source branches are preserved byte-for-byte as Git tree snapshots before branch deletion:

- `archive/donors/chat-bridge-event-wake/` — original head `4c71281d4f192ad9b874cd52d1fedba971347776`, tree `738d2ef5b42157857b2d647444e7466d10814f1c`.
- `archive/donors/openworker-governance/` — original head `32beb23bf73491413860e64df5c4bf8327c3c200`, tree `91cfb94ca5c3b4f933c17fde948d96a4d902bf1a`.
- `archive/donors/conversation-fabric-superchat/` — original head `cc4469fdb046425423c0506e6898aa1606b4f6d3`, tree `1e279b05dbdc7e25542a025e66e5f117a48537e0`.
- `archive/donors/consolidated-development-roadmap/` — original head `d5d727f219d7063d2e5294462a867ae1351abcf4`, tree `71e8478449ec57f37ecf409a6a428908cec9d012`.

The snapshots preserve all donor code, tests, docs, and evidence without making old central runtime files authoritative.

## Event Wake conflict policy

Do not overwrite current Chat Bridge worker/content/recovery owners with the older Event Wake versions. Those files predate the latest assistant-timeout/transient recovery changes. Their exact source is retained in the donor snapshot for selective future porting.

The safe active pieces have already been lifted out: Python result-event outbox/native host and the pure JS event-wake state model. Future event delivery/routing must be implemented against current canonical Bridge owners and prove the existing timeout/transient recovery contracts remain green.

## Branch deletion readiness

After the canonical branch CI is green, the following development branches contain no information that exists only as an unpreserved branch ref and are safe to delete:

- `feature/chat-bridge-event-wake`
- `feature/openworker-governance`
- `feature/conversation-fabric-superchat`
- `plan/consolidated-development-roadmap`
- `work/chat-bridge-live-chat-states`
- `maintenance/transient-recovery-patch`
- `work/transient-recovery-validation`

Draft PRs #77, #81, and #85 should be closed as superseded by `develop/conversation-fabric`, not merged.
