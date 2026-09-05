# Contributing to Local Agent

Local Agent is execution infrastructure. Changes should favor **deterministic behavior, bounded execution, explicit failure and recoverable state** over clever implicit recovery.

Before changing runtime behavior, read:

1. [`AGENTS.md`](AGENTS.md) — normative repository rules and safety invariants;
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module ownership and dependency direction;
3. [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — production workflow and release gates;
4. [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) — trust boundaries and non-goals.

## Development setup

Local Agent intentionally has a small dependency surface. Runtime code is primarily Python standard library plus the zero-dependency Chat Bridge JavaScript.

For development tooling, create a virtual environment and install the pinned lint/coverage tools used by CI:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install ruff==0.12.11 coverage==7.16.0
```

Ruff policy lives in [`pyproject.toml`](pyproject.toml). Tool upgrades should be deliberate migrations, not silent changes to the lint contract.

## One verification command

Run the complete repository verifier:

```bash
.venv/bin/python scripts/verify.py
```

During iteration, run the narrowest useful stage:

```bash
.venv/bin/python scripts/verify.py --only compile
.venv/bin/python scripts/verify.py --only lint
.venv/bin/python scripts/verify.py --only bridge
.venv/bin/python scripts/verify.py --only tests
```

Focused macOS/supervisor smoke:

```bash
.venv/bin/python scripts/verify.py --profile macos-smoke
```

CI additionally measures branch-aware coverage and runs the Python suite on Python 3.14.

## What deserves a test

Add targeted coverage for behavior that can change execution, safety or recovery semantics. Examples:

- hard-binding admission and rejection;
- task/resource contract validation;
- worker/supervisor exit-code interpretation;
- retry/backoff and starvation prevention;
- process-group lifecycle and inherited lease descriptors;
- crash/publication recovery;
- timeout/no-output/RSS behavior;
- emergency disable/cancel semantics;
- repository provisioning and identity validation.

Do not add tests merely to raise a global coverage number. Coverage is used to find risk concentrations, not as a substitute for meaningful assertions.

## Architecture rules

New reusable implementation belongs under `local_agent/`, not in another large root module.

Prefer these directions:

```text
root CLI/entrypoint
    ↓
local_agent supervisor/operator/repository/runtime/platform
    ↓
low-level process/storage foundations
```

Avoid introducing package-to-root imports when an equivalent packaged dependency exists. Temporary compatibility aliases created during the architecture migration should be removed once all real callers have moved.

Keep modules cohesive. A file should have a clear owner role rather than becoming a collection of unrelated helpers.

## Runtime change workflow

For non-trivial runtime work:

1. start from current `main`;
2. use an isolated `work/...` branch;
3. make the smallest coherent change;
4. run focused regression checks;
5. add/adjust targeted tests for changed semantics;
6. run the full CI matrix on the exact candidate SHA;
7. review the complete `main...candidate` diff;
8. audit affected downstream Local Agent documentation/contracts;
9. merge only after the candidate is green;
10. restart the live service only during a safe/idle window and verify live evidence.

Do not use the live production checkout as an experimental worktree while it is servicing autonomous tasks.

## Git and publication discipline

- Do not rewrite published task/result identity.
- Keep generated runtime state out of normal source commits.
- Do not use broad `git add -A` in executor publication logic.
- Keep candidate branches temporary; remove them after the release is established.
- Prefer focused commits whose message explains the behavior or boundary being changed.

## Safety-sensitive changes

Changes involving any of the following require focused negative-path tests in addition to happy-path coverage:

- agent binding;
- operator disable/re-enable;
- active task cancellation;
- process termination;
- repository/resource locking;
- claim recovery;
- self-update/restart;
- destructive cleanup/reset;
- control-plane path validation.

A refactor must preserve safety semantics even when no user-visible feature changes.

## macOS deployment

Do not commit a plist containing developer-specific absolute paths. Use the generator documented in [`deploy/macos/README.md`](deploy/macos/README.md):

```bash
.venv/bin/python scripts/macos_launchd.py render
.venv/bin/python scripts/macos_launchd.py install --mode parallel --max-workers 2
```

`install` writes configuration without restarting the service. `restart` is intentionally a separate disruptive command.

## Pull request notes

A useful runtime PR should state:

- what contract/behavior changed;
- why the change is needed;
- safety implications;
- focused verification performed;
- full CI evidence;
- whether downstream docs changed;
- whether a live restart/E2E is required after merge.

For architecture-only movement, explicitly state whether runtime behavior is intended to remain unchanged and call out any temporary compatibility surface that remains.
