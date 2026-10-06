# Local host profile

## Purpose

`python -m local_agent.host_ops host profile` returns a small vendor-neutral fact set that Local Agent can use when deciding whether a machine is suitable for a task. It reports facts only; target selection and scheduling remain outside `host-ops`.

```bash
python -m local_agent.host_ops host profile
python -m local_agent.host_ops host profile --json
```

The profile contains:

- hostname;
- operating-system name and release;
- architecture;
- logical CPU count when available;
- total physical memory when available;
- GPU device names when the platform exposes them through the bounded host profile;
- total and free capacity of the root filesystem.

## Platform behavior

Most facts use Python standard-library host APIs. On macOS, total physical memory is read through pinned `/usr/sbin/sysctl -n hw.memsize` under the shared bounded `ProcessRunner`. GPU identity is read best-effort through pinned `/usr/sbin/system_profiler -json -detailLevel mini SPDisplaysDataType` under the same limits. The `mini` detail level avoids collecting unnecessary display detail and reduces bounded-output pressure. Invalid, failed or truncated GPU inspection reports `gpu_devices=null` without failing the otherwise trustworthy host profile; a valid empty inventory reports `gpu_devices=[]`.

On Linux, physical memory is derived from `sysconf` when the platform exposes valid page-count/page-size values. GPU discovery is not yet implemented there, so `gpu_devices=null`. Other unsupported platforms may likewise report optional fields as `null` while still returning the remaining facts.

The capability does not benchmark the machine, infer workload suitability, reserve resources or schedule work. Those decisions belong to ChatGPT/Local Agent.
