from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from local_agent.foundation.control_git_lock import (
    CONTROL_GIT_LOCK_FILENAME,
    DynamicControlGitLock,
    control_git_lock,
)


class ControlGitLockTests(unittest.TestCase):
    def make_control(self, root: Path, name: str) -> Path:
        control = root / name
        (control / ".git").mkdir(parents=True)
        return control

    def test_same_checkout_returns_same_reentrant_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control = self.make_control(Path(directory), "control")
            first = control_git_lock(control)
            second = control_git_lock(control)
            self.assertIs(first, second)
            with first:
                with second:
                    self.assertTrue(
                        (control / ".git" / CONTROL_GIT_LOCK_FILENAME).is_file()
                    )

    def test_missing_git_directory_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control = Path(directory) / "missing-control"
            control.mkdir()
            with self.assertRaisesRegex(RuntimeError, "normal Git checkout"):
                with control_git_lock(control):
                    self.fail("lock unexpectedly admitted a non-Git checkout")

    def test_dynamic_lock_resolves_current_checkout_on_each_outer_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.make_control(root, "first")
            second = self.make_control(root, "second")
            current = [first]
            lock = DynamicControlGitLock(lambda: current[0])

            with lock:
                self.assertTrue((first / ".git" / CONTROL_GIT_LOCK_FILENAME).exists())
                current[0] = second
                with lock:
                    self.assertFalse(
                        (second / ".git" / CONTROL_GIT_LOCK_FILENAME).exists()
                    )

            with lock:
                self.assertTrue((second / ".git" / CONTROL_GIT_LOCK_FILENAME).exists())

    def test_lock_serializes_independent_processes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = self.make_control(root, "control")
            started = root / "child-started"
            acquired = root / "child-acquired"
            script = """
import sys
from pathlib import Path
from local_agent.foundation.control_git_lock import control_git_lock

control = Path(sys.argv[1])
started = Path(sys.argv[2])
acquired = Path(sys.argv[3])
started.write_text('started', encoding='utf-8')
with control_git_lock(control):
    acquired.write_text('acquired', encoding='utf-8')
"""

            with control_git_lock(control):
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        script,
                        str(control),
                        str(started),
                        str(acquired),
                    ],
                    cwd=Path.cwd(),
                )
                deadline = time.monotonic() + 5.0
                while not started.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(started.exists(), "child did not reach lock acquisition")
                time.sleep(0.05)
                self.assertFalse(acquired.exists())

            child.wait(timeout=5.0)
            self.assertEqual(child.returncode, 0)
            self.assertEqual(acquired.read_text(encoding="utf-8"), "acquired")

    def test_lock_serializes_threads_via_reentrant_process_guard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control = self.make_control(Path(directory), "control")
            lock = control_git_lock(control)
            entered = threading.Event()
            release = threading.Event()

            def worker() -> None:
                with lock:
                    entered.set()
                    release.wait(timeout=5.0)

            with lock:
                thread = threading.Thread(target=worker)
                thread.start()
                self.assertFalse(entered.wait(timeout=0.1))
            self.assertTrue(entered.wait(timeout=1.0))
            release.set()
            thread.join(timeout=2.0)
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
