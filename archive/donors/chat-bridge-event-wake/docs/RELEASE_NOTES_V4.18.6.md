# Local Agent 4.18.6

Local Agent 4.18.5 fixed orphaned repository lease recovery and improved launchd diagnostics, but a production restart exposed a separate macOS launchd race. `launchctl bootout` can return before the previous LaunchAgent instance is fully forgotten. The restart helper immediately called `launchctl bootstrap`, which could then fail transiently with exit code 5, `Input/output error` and `Bad request`, leaving the service unloaded even though the plist itself was valid.

## Hardening

The macOS restart path now:

- waits for `launchctl print gui/<uid>/com.michal.local-agent` to report the previous service absent after `bootout`;
- fails closed if the previous service does not disappear within a bounded timeout;
- retries `bootstrap` only for the observed transient exit-5 `Bad request` / `Input/output error` condition;
- confirms the service is still absent before any retry, avoiding a duplicate bootstrap if launchd actually loaded it despite returning an error;
- keeps non-transient bootstrap errors visible and does not retry malformed plist or other configuration failures.

## Regression coverage

The macOS launchd unit suite now covers:

- polling until an old service disappears;
- bounded unload timeout;
- retry of the observed transient `bootstrap` failure;
- no retry for unrelated launchd/bootstrap errors.

This release does not change task routing, repository leases, planner contracts, concurrency, bindings, resources, status/result formats or repository control semantics. It only hardens macOS LaunchAgent restart behavior.
