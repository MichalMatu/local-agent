## What changed

<!-- Describe the behavior, contract or architecture boundary changed by this PR. -->

## Why

<!-- Explain the problem and why this is the smallest coherent solution. -->

## Safety impact

- [ ] No executor safety invariant changes.
- [ ] Hard binding / repository identity reviewed if relevant.
- [ ] Process, lease, watchdog or recovery semantics reviewed if relevant.
- [ ] Emergency control semantics reviewed if relevant.
- [ ] Destructive paths have explicit negative-path coverage if relevant.

<!-- If any box above is not applicable, say why. If behavior intentionally changes, describe the new invariant. -->

## Verification

### Focused

```text
<commands / tests / evidence>
```

### Full candidate

- [ ] compile
- [ ] Ruff
- [ ] Chat Bridge validation/tests
- [ ] Python unit/integration suite
- [ ] Python 3.14 compatibility
- [ ] macOS smoke when runtime/process/deployment behavior is affected

## Coverage / regression evidence

<!-- Mention meaningful risk-path coverage changes; do not chase a vanity percentage. -->

## Documentation / downstream contract

- [ ] Root/docs updated where behavior or architecture changed.
- [ ] Registered downstream planner docs audited if the Local Agent contract changed.
- [ ] No downstream update is needed (explain why).

## Deployment / live validation

- [ ] No live daemon restart required.
- [ ] Live restart/E2E required after merge during a safe idle window.

<!-- Never interrupt an active production task merely to validate a candidate. -->

## Temporary migration surface

<!-- List compatibility aliases, staging code or follow-up cleanup that remains after this PR. -->
