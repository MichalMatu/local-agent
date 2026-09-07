from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import local_agent.foundation.process as agent_process
from local_agent import entrypoint
from local_agent.foundation.lease_recovery import (
    recover_orphaned_repository_leases,
    repository_leases_busy,
)
from local_agent.foundation.process import (
    LEASE_FDS_ENV,
    LEASE_KEYS_DIGEST_ENV,
    RESOURCE_LEASE_FDS_ENV,
    acquire_execution_leases,
    popen_registered,
    unregister_process,
)


class LeaseRecoveryTests(unittest.TestCase):
    def tearDown(self) -> None:
        agent_process.reset_process_lifecycle_for_tests()

    def test_busy_probe_does_not_require_lease_metadata_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "locks"
            leases = acquire_execution_leases(lock_dir, ("repository:one",))
            try:
                self.assertTrue(repository_leases_busy(leases.paths))
            finally:
                leases.close()
            self.assertFalse(repository_leases_busy(leases.paths))

    def test_orphan_recovery_kills_only_actual_lock_holder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_dir = root / "locks"
            leases = acquire_execution_leases(lock_dir, ("repository:one",))
            env = os.environ.copy()
            env.update(leases.environment())
            holder_code = (
                "import signal,time; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "print('holder-ready', flush=True); "
                "time.sleep(60)"
            )
            holder = popen_registered(
                [sys.executable, "-c", holder_code],
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            observer: subprocess.Popen[str] | None = None
            try:
                assert holder.stdout is not None
                self.assertEqual(holder.stdout.readline().strip(), "holder-ready")
                paths = leases.paths
                leases.close()
                self.assertTrue(repository_leases_busy(paths))

                observer_env = os.environ.copy()
                for name in (LEASE_FDS_ENV, LEASE_KEYS_DIGEST_ENV, RESOURCE_LEASE_FDS_ENV):
                    observer_env.pop(name, None)
                observer_code = (
                    "import sys,time; "
                    "handle=open(sys.argv[1], 'r'); "
                    "print('observer-ready', flush=True); "
                    "time.sleep(60)"
                )
                observer = popen_registered(
                    [sys.executable, "-c", observer_code, str(paths[0])],
                    cwd=root,
                    env=observer_env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
                assert observer.stdout is not None
                self.assertEqual(observer.stdout.readline().strip(), "observer-ready")

                recovered = recover_orphaned_repository_leases(
                    paths,
                    log=lambda _message: None,
                    grace_seconds=0.1,
                )
                self.assertEqual(recovered, (holder.pid,))
                holder.wait(timeout=5)
                self.assertNotEqual(holder.returncode, 0)
                self.assertIsNone(observer.poll())
                self.assertFalse(repository_leases_busy(paths))

                reacquired = acquire_execution_leases(lock_dir, ("repository:one",))
                reacquired.close()
            finally:
                if holder.poll() is None:
                    holder.kill()
                    holder.wait(timeout=5)
                if holder.stdout is not None:
                    holder.stdout.close()
                unregister_process(holder)
                if observer is not None:
                    if observer.poll() is None:
                        observer.kill()
                        observer.wait(timeout=5)
                    if observer.stdout is not None:
                        observer.stdout.close()
                    unregister_process(observer)


class EntrypointLeaseWatchdogTests(unittest.TestCase):
    def test_quiescent_status_must_belong_to_current_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / "status.json"
            status.write_text(
                json.dumps(
                    {
                        "state": "idle",
                        "supervisor_pid": 1234,
                        "active_repository_ids": [],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(entrypoint.agentd, "LOCAL_STATUS_PATH", status):
                self.assertTrue(entrypoint._supervisor_reports_quiescent(1234))
                self.assertFalse(entrypoint._supervisor_reports_quiescent(5678))

    def test_running_repository_is_not_quiescent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / "status.json"
            status.write_text(
                json.dumps(
                    {
                        "state": "running",
                        "supervisor_pid": 1234,
                        "active_repository_ids": ["tracker"],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(entrypoint.agentd, "LOCAL_STATUS_PATH", status):
                self.assertFalse(entrypoint._supervisor_reports_quiescent(1234))

    def test_global_control_status_is_not_quiescent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / "status.json"
            status.write_text(
                json.dumps(
                    {
                        "state": "idle",
                        "supervisor_pid": 1234,
                        "active_repository_ids": [],
                        "supervisor_control_repository": "litegraph",
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(entrypoint.agentd, "LOCAL_STATUS_PATH", status):
                self.assertFalse(entrypoint._supervisor_reports_quiescent(1234))

    def test_orphan_recovery_guard_refuses_live_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "agentd.lock"
            handle = lock_path.open("a+", encoding="utf-8")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with mock.patch.object(entrypoint.agentd, "DAEMON_LOCK_PATH", lock_path):
                    with self.assertRaisesRegex(RuntimeError, "refusing orphan recovery"):
                        with entrypoint._orphan_recovery_guard():
                            self.fail("guard must not enter while another daemon owns the lock")
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()


if __name__ == "__main__":
    unittest.main()
