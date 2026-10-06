# ADB operations

## Purpose

`host-ops` exposes bounded, device-scoped Android Debug Bridge operations for Local Agent. The exact ADB serial is always explicit; there is no device registry and no arbitrary shell surface.

## Commands

```bash
python -m local_agent.host_ops adb devices --json
python -m local_agent.host_ops adb identity R58N123ABC --json
python -m local_agent.host_ops adb logcat R58N123ABC --lines 200 --json
python -m local_agent.host_ops adb push R58N123ABC ./artifact.bin /sdcard/Download/artifact.bin --json
python -m local_agent.host_ops adb pull R58N123ABC /sdcard/Download/result.bin ./result.bin --json
```

`devices` runs bounded `adb devices -l`. `identity` proves the explicit serial is ready and reads the fixed `getprop` identity set. `logcat` first proves readiness and uses only bounded `adb logcat -d -t N`.

Verified file transfer is intentionally narrower than a general Android filesystem API. Remote paths must be normalized absolute POSIX file paths with conservative literal characters. Push stages in the destination directory, verifies byte size and SHA-256, then performs replace or no-clobber commit and verifies the final destination again. Pull verifies the remote source before and after transfer, stages locally, fsyncs the file, commits atomically/no-clobber, and reports directory-fsync evidence. Existing destinations require explicit `--replace`.

## Safety boundary

- the ADB executable is resolved explicitly from `PATH` and invoked through the shared `ProcessRunner`;
- every device-scoped operation supplies validated `-s SERIAL`;
- stdout/stderr and whole-operation execution are bounded;
- discovery/property/logcat truncation fails closed;
- transfer size is bounded (512 MiB default, explicit override supported);
- transfer source/destination symlinks and path traversal are rejected;
- SHA-256 and byte-size evidence are checked around transfer/commit;
- staging is cleaned on pre-commit push failures and local pull staging is removed on failure;
- there is no arbitrary `adb shell`, package mutation, reboot or install/uninstall command.

The transfer implementation uses a fixed internal remote command set (`test`, `wc`, SHA-256 tooling, `mv`, `rm`) only for the validated literal paths needed to prove and commit one file transfer.
