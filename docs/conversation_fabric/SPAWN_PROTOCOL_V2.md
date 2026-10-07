# Spawn protocol v2 — page-local transaction model

Status: **contract-only, inactive**. `spawn_phase_model.js` is intentionally
not imported by the extension. This slice does not change child creation,
message submission, browser storage, or existing production recovery.

The existing content script writes its session claim after composer mutation.
That ordering is unsafe as a general restart boundary: a process/page
interruption can leave an unclaimed draft. The v2 integration must instead
persist the exact transaction identity **before the first composer mutation**.

## Monotonic phases

`prepared -> draft_verified -> submit_armed -> submitted -> response_started`

- `prepared`: page-local claim exists, persisted and read back before writing
  any draft. It contains the immutable transaction id and request/bootstrap
  digests.
- `draft_verified`: the exact draft was read back from the single visible,
  current composer.
- `submit_armed`: irreversible boundary. Persist and read back **before**
  any click/Send; no future retry, new tab, or second Send.
- `submitted`: submit action was invoked; any uncertain acknowledgement or
  browser restart must be reconciled using exact tab/route/message evidence.
- `response_started`: child response observed, not simply a known URL.

Only adjacent monotonic advances are allowed. Re-reading the same state is
idempotent. Explicit retry is permitted only in `prepared` or
`draft_verified`, bounded to 32 attempts. A same transaction identity with a
different request/bootstrap digest is permanently conflicting.

## Integration gates

1. Use an exact page-local claim persisted and read back before **both**
   clearing an old owned draft and writing a new draft. Failed persistence
   must prevent composer mutation.
2. `findComposer()` must select one visible/current composer in the active
   composer form, rejecting hidden, stale, ambiguous, or duplicate nodes.
3. Arm in page storage and verify readback before Send. From
   `submit_armed` forward only reconcile the **original** tab. No
   speculative replacement and no repeated Send after restart/timeout.
4. Recover `draft_verified` by comparing exact text and identity. A claim
   from another request must never clear or overwrite composer content.
5. Keep immutable browser intent fields, ChildRequest digest, bootstrap SHA,
   tab ownership evidence, original worker claim and bounded budgets intact.
6. Pass isolated Chromium failure injection for interruption before claim,
   after claim, during draft writing, immediately after arm, during click,
   after route transition, and during response observation.
7. After tests, perform opt-in real browser smoke in the managed Chrome
   profile. The GitHub dispatch intake remains a **separate** gate.

The pure model asserts allowed phases and fail-closed transitions, but it
cannot prove browser atomicity or real tab identity on its own. Do not enable
it in production until all seven integration gates pass.
