from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from tests.test_multirepo_crash_recovery import process_alive, wait_for_process_exit
from tests.test_multirepo_integration import REPO_ROOT


class GuardProcessTests(unittest.TestCase):
    def test_guard_sigterm_and_unexpected_error_reap_registered_supervisor(self) -> None:
        for failure in ("sigterm", "exception"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                child_pid_file = root / "child.pid"
                ready = root / "ready"
                child_code = f"import os,time; from pathlib import Path; Path({str(child_pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)"
                code = textwrap.dedent(f"""
                    import sys
                    from pathlib import Path
                    from local_agent import entrypoint
                    from local_agent.foundation import process
                    entrypoint.agent_remote_operator.poll_remote_operator = lambda *_a, **_k: None
                    entrypoint.agent_operator.is_disabled = lambda: False
                    entrypoint.load_repository_registry = lambda **_k: [object()]
                    entrypoint.prepare_repositories = lambda _r: None
                    entrypoint.supervisor_command = lambda _a: [sys.executable, '-c', {child_code!r}]
                    calls = 0
                    def revision():
                        global calls
                        calls += 1
                        if calls > 2:
                            Path({str(ready)!r}).touch()
                            if {failure!r} == 'exception':
                                raise RuntimeError('injected guard failure')
                        return 'stable'
                    entrypoint.agentd.self_revision = revision
                    try:
                        entrypoint.main()
                    except RuntimeError as exc:
                        assert str(exc) == 'injected guard failure'
                    assert not process._active_processes
                """)
                with (root / "guard.log").open("w+") as log:
                    guard = subprocess.Popen(
                        [sys.executable, "-c", code],
                        cwd=REPO_ROOT,
                        env=dict(os.environ, HOME=tmp),
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                    child_pid = None
                    try:
                        deadline = time.monotonic() + 10
                        while not ready.exists() and time.monotonic() < deadline:
                            time.sleep(0.05)
                        self.assertTrue(ready.exists())
                        child_pid = int(child_pid_file.read_text())
                        if failure == "sigterm":
                            self.assertTrue(process_alive(child_pid))
                            guard.send_signal(signal.SIGTERM)
                        guard.wait(timeout=10)
                        log.seek(0)
                        self.assertEqual(guard.returncode, 0, log.read())
                        wait_for_process_exit(child_pid, timeout=5)
                    finally:
                        if guard.poll() is None:
                            guard.kill()
                        guard.wait(timeout=5)
                        if child_pid is not None and process_alive(child_pid):
                            os.killpg(child_pid, signal.SIGKILL)
                            wait_for_process_exit(child_pid, timeout=5)


if __name__ == "__main__":
    unittest.main()
