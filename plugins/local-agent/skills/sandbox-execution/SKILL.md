---
name: sandbox-execution
description: Prefer the ChatGPT sandbox for reproducible software-only builds and tests when the repository provides an exact source snapshot and compatible offline dependency pack, using ChatGPT Library for persistent cache artifacts.
---

# Sandbox-first execution workflow

Use this workflow when the requested evidence does not require the user's physical computer, private local files, local services, or attached hardware.

The default worker order is:

1. direct GitHub inspection/editing for source changes;
2. ChatGPT sandbox for software-only compilation and tests when reproducible inputs are available;
3. GitHub Actions for canonical networked CI and dependency-pack generation;
4. Local Agent only for genuinely machine-specific or hardware-specific evidence.

Do not consume the user's local CPU/RAM merely because a task is a build or test when the sandbox can reproduce the required environment.

## Repository contract

Before using the sandbox, inspect the target repository for its current sandbox instructions. Prefer repository-owned files such as:

```text
docs/SANDBOX_EXECUTION_FLOW.md
tools/sandbox/
.github/workflows/sandbox-pack.yml
```

Repository instructions own the exact toolchain, dependency key, cache layout, bootstrap commands, and verification profiles. Do not invent a second build system in the plugin.

## Source-of-truth and identity

GitHub remains the source of truth. A Library source snapshot is only a transport artifact.

For every sandbox run:

1. resolve one explicit repository and exact target Git SHA;
2. obtain the matching source snapshot from ChatGPT Library or a trusted GitHub Actions artifact;
3. verify the snapshot checksum before extraction when a checksum is provided;
4. verify the embedded source SHA after extraction;
5. refuse to test a snapshot whose embedded SHA differs from the intended revision.

Never claim a sandbox result for a different source revision.

## Persistent ChatGPT Library cache

When the current ChatGPT surface exposes Library/file access, use the repository's documented Library folder and naming scheme for persistent bootstrap/cache assets.

A good repository-owned pattern is:

```text
/<Project>/Sandbox/
  <project>-source-<git-sha>.tar.zst
  <project>-source-<git-sha>.tar.zst.sha256
  <project>-offline-<dependency-key>/
    manifest/
    part-00
    part-01
    ...
```

The offline pack should contain only reusable development dependencies required to reconstruct the environment, for example package-manager caches, wheelhouses, compiler/SDK caches, or browser binaries.

Do not store secrets, tokens, signing material, cookies, production databases, private user data, local `.env` files, or machine credentials in Library dependency packs.

If Library/file access is unavailable on the current surface, do not pretend the cache is available. Use the repository's documented GitHub Actions artifact path or fall back to canonical CI/Local Agent according to the worker-selection rules.

## Dependency packs

Dependency packs must be keyed by the inputs that affect environment compatibility, such as lockfiles, requirements files, toolchain versions, bootstrap scripts, SDK versions, or build configuration.

Source-only changes should not invalidate a dependency pack.

When dependency inputs change, generate a new immutable dependency-key pack. Do not silently mutate an older pack in place.

For sandboxes without reliable network access, restore dependencies only from the compatible offline pack. A missing dependency is a cache/CI issue, not permission to change dependency versions or download arbitrary replacements.

## Bootstrap into the sandbox

Use `/mnt/data` or the current sandbox workspace for ephemeral execution state. Keep persistent artifacts in Library, not in the sandbox filesystem.

Typical flow:

```text
Library/GitHub artifact
  -> verify checksum
  -> copy/materialize into sandbox
  -> extract exact source snapshot
  -> verify embedded Git SHA
  -> reconstruct environment from offline dependency pack
  -> run repository-owned sandbox doctor/bootstrap
  -> run focused verification first
  -> broaden only when useful
```

Never assume a fresh sandbox retains files from a previous conversation or execution environment.

## Verification ladder

Prefer the cheapest useful evidence first:

1. changed-file/static inspection;
2. one affected test or compile target;
3. repository sandbox backend/frontend/module profile;
4. repository broad sandbox check;
5. exact-SHA GitHub Actions result;
6. Local Agent only when sandbox/CI cannot reproduce the needed machine-specific evidence.

A sandbox pass does not replace canonical CI when the repository defines CI as the release/main gate.

## When to switch to Local Agent

Use Local Agent instead of the sandbox for tasks requiring any of the following:

- USB, serial, BLE, ADB, phones, microcontrollers, or other attached hardware;
- machine-local files or data intentionally needed for the task;
- local services, credentials, or production-like state that must not be copied to Library;
- platform-specific behavior that cannot be reproduced by the sandbox;
- toolchains or dependencies for which no compatible sandbox/offline pack exists and repository policy requires local evidence.

Do not upload private machine state to Library merely to avoid using Local Agent.

## Established reference implementations

The current repository ecosystem already contains two useful patterns:

- `MichalMatu/photomap`: full sandbox-first flow with exact source snapshots, Python/npm/Playwright offline dependency packs, checksums, split Library artifacts, sandbox bootstrap/doctor wrappers, and GitHub Actions generation;
- `MichalMatu/tracker`: Android/JDK 21 sandbox flow with exact source snapshots, Gradle/Android SDK offline caches, isolated sandbox state, and Local Agent reserved for ADB/Bluetooth/physical-device evidence.

Use these as architectural references, not as hard-coded dependencies. Product users must operate on their own repositories and their own GitHub accounts.
