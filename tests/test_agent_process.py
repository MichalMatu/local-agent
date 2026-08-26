from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import agent_process
from agent_process import (
    BoundedTextBuffer,
    ExecutionLeaseBusy,
    acquire_execution_leases,
    process_group_for,
    spawn_shell,
    terminate_active_processes,
    terminate_process_group,
    unregister_process,
)


class BoundedTextBufferTests(unittest.TestCase):
    def test_buffer_keeps_exact_tail_across_chunks(self) -> None:
        buffer = BoundedTextBuffer(8)
        buffer.append("abc")
        buffer.append("defgh")
        buffer.append("ij")
        self.assertEqual(buffer.text(), "cdefghij")
        self.assertEqual(len(buffer), 8)

    def test_single_large_chunk_is_strictly_bounded(self) -> None:
        buffer = BoundedTextBuffer(5)
        buffer.append("0123456789")
        self.assertEqual(buffer.text(), "56789")
        self.assertEqual(len(buffer), 5)


class ProcessGroupTests(unittest.TestCase):
    def tearDown(self) -> None:
        agent_process.reset_process_lifecycle_for_tests()

    def test_stored_process_group_survives_parent_exit(self) -> None:
        proc = mock.Mock(spec=subprocess.Popen)
        proc.pid = 123
        proc.poll.return_value = 0
        setattr(proc, "_local_agent_process_group", 456)
        self.assertEqual(process_group_for(proc), 456)

    def test_terminate_escalates_when_group_remains_alive(self) -> None:
        proc = mock.Mock(spec=subprocess.Popen)
        proc.pid = 123
        setattr(proc, "_local_agent_process_group", 456)
        log = mock.Mock()
        with mock.patch("agent_process.os.getpgrp", return_value=999), mock.patch(
            "agent_process.os.killpg"
        ) as killpg, mock.patch(
            "agent_process.process_group_alive", side_effect=[True, True, True]
        ), mock.patch("agent_process.time.monotonic", side_effect=[0.0, 0.0, 1.0]), mock.patch(
            "agent_process.time.sleep"
        ):
            terminate_process_group(proc, log, grace_seconds=0.5)

        self.assertEqual(killpg.call_args_list[0].args[0], 456)
        self.assertEqual(killpg.call_args_list[-1].args[0], 456)
        self.assertEqual(killpg.call_count, 2)

    def test_terminate_active_processes_stops_real_registered_group(self) -> None:
        proc = spawn_shell("sleep 30", cwd=Path.cwd(), env=os.environ)
        try:
            self.assertEqual(
                terminate_active_processes(
                    lambda _message: None,
                    grace_seconds=0.2,
                ),
                1,
            )
            proc.wait(timeout=5)
            self.assertIsNotNone(proc.returncode)
        finally:
            if proc.poll() is None:
                terminate_process_group(proc, lambda _message: None, grace_seconds=0.1)
            if proc.stdout is not None:
                proc.stdout.close()
            unregister_process(proc)

    def test_terminate_active_processes_tolerates_unreachable_exited_group(self) -> None:
        proc = mock.Mock(spec=subprocess.Popen)
        proc.pid = 12345
        proc.poll.return_value = -signal.SIGKILL
        with mock.patch("agent_process.subprocess.Popen", return_value=proc):
            agent_process.popen_registered(["ignored"], start_new_session=True)
        with mock.patch("agent_process.os.getpgrp", return_value=99999), mock.patch(
            "agent_process.os.killpg",
            side_effect=PermissionError(1, "operation not permitted"),
        ):
            self.assertEqual(
                terminate_active_processes(lambda _message: None, grace_seconds=0.0),
                1,
            )

    def test_signal_during_spawn_is_redelivered_after_registration(self) -> None:
        proc = mock.Mock(spec=subprocess.Popen)
        proc.pid = 12345
        proc.poll.return_value = 0
        deliveries: list[str] = []
        previous = signal.getsignal(signal.SIGUSR1)

        def handler(signum: int, _frame: object) -> None:
            if agent_process.defer_termination_during_spawn(signum):
                deliveries.append("deferred")
                return
            deliveries.append("delivered")
            raise SystemExit(128 + signum)

        def spawn(*_args: object, **_kwargs: object) -> mock.Mock:
            os.kill(os.getpid(), signal.SIGUSR1)
            return proc

        signal.signal(signal.SIGUSR1, handler)
        try:
            with mock.patch("agent_process.subprocess.Popen", side_effect=spawn):
                with self.assertRaisesRegex(SystemExit, str(128 + signal.SIGUSR1)):
                    agent_process.popen_registered(
                        ["ignored"],
                        start_new_session=True,
                    )
        finally:
            signal.signal(signal.SIGUSR1, previous)

        self.assertEqual(deliveries, ["deferred", "delivered"])
        self.assertEqual(process_group_for(proc), proc.pid)


class ExecutionLeaseTests(unittest.TestCase):
    def tearDown(self) -> None:
        agent_process.reset_process_lifecycle_for_tests()

    def test_second_open_description_cannot_acquire_held_lease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "locks"
            first = acquire_execution_leases(lock_dir, ("repository:one",))
            try:
                with self.assertRaises(ExecutionLeaseBusy):
                    acquire_execution_leases(lock_dir, ("repository:one",))
            finally:
                first.close()
            second = acquire_execution_leases(lock_dir, ("repository:one",))
            second.close()

    def test_failed_lease_metadata_write_releases_already_acquired_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "locks"
            with mock.patch(
                "agent_process.os.fsync",
                side_effect=OSError("fsync failed"),
            ):
                with self.assertRaisesRegex(OSError, "fsync failed"):
                    acquire_execution_leases(lock_dir, ("repository:one",))
            acquired = acquire_execution_leases(lock_dir, ("repository:one",))
            acquired.close()

    def test_inherited_lease_survives_owner_close_until_child_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "locks"
            leases = acquire_execution_leases(lock_dir, ("repository:one",))
            child_env = dict(os.environ)
            child_env.update(leases.environment())
            proc = spawn_shell("sleep 30", cwd=Path(tmp), env=child_env)
            leases.close()
            try:
                with self.assertRaises(ExecutionLeaseBusy):
                    acquire_execution_leases(lock_dir, ("repository:one",))
                terminate_process_group(proc, lambda _message: None, grace_seconds=0.1)
                proc.wait(timeout=5)
                deadline = time.monotonic() + 5
                while True:
                    try:
                        acquired = acquire_execution_leases(
                            lock_dir,
                            ("repository:one",),
                        )
                    except ExecutionLeaseBusy:
                        if time.monotonic() >= deadline:
                            self.fail("lease remained held after child termination")
                        time.sleep(0.05)
                    else:
                        acquired.close()
                        break
            finally:
                if proc.poll() is None:
                    terminate_process_group(proc, lambda _message: None, grace_seconds=0.1)
                if proc.stdout is not None:
                    proc.stdout.close()
                unregister_process(proc)


if __name__ == "__main__":
    unittest.main()
