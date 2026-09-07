from __future__ import annotations

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
from local_agent.foundation.process import acquire_execution_leases, popen_registered, unregister_process


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

    def test_orphan_recovery_escalates_and_releases_inherited_lease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_dir = root / "locks"
            leases = acquire_execution_leases(lock_dir, ("repository:one",))
            env = os.environ.copy()
            env.update(leases.environment())
            code = (
                "import signal,time; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "print('ready', flush=True); "
                "time.sleep(60)"
            )
            proc = popen_registered(
                [sys.executable, "-c", code],
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            try:
                assert proc.stdout is not None
                self.assertEqual(proc.stdout.readline().strip(), "ready")
                paths = leases.paths
                leases.close()
                self.assertTrue(repository_leases_busy(paths))

                recovered = recover_orphaned_repository_leases(
                    paths,
                    log=lambda _message: None,
                    grace_seconds=0.1,
                )
                self.assertIn(proc.pid, recovered)
                proc.wait(timeout=5)
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(repository_leases_busy(paths))

                reacquired = acquire_execution_leases(lock_dir, ("repository:one",))
                reacquired.close()
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
                if proc.stdout is not None:
                    proc.stdout.close()
                unregister_process(proc)


class EntrypointLeaseWatchdogTests(unittest.TestCase):
    def test_quiescent_status_must_belong_to_current_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / "status.json"
            status.write_text(
                json.dumps(
                    {
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
                        "supervisor_pid": 1234,
                        "active_repository_ids": ["tracker"],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(entrypoint.agentd, "LOCAL_STATUS_PATH", status):
                self.assertFalse(entrypoint._supervisor_reports_quiescent(1234))


if __name__ == "__main__":
    unittest.main()
