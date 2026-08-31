from __future__ import annotations

import contextlib
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import agent_parallel as parallel
import agentd
from tests.test_multirepo_integration import (
    REPO_ROOT,
    configure_identity,
    create_repository_fixture,
    git,
    test_environment,
    write_registry,
)


def wait_for_path(path: Path, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {path}")


def configure_blocking_control_task(
    item: dict[str, Path | str],
    *,
    started: Path,
    release: Path,
) -> None:
    control = Path(item["control"])
    task_path = control / ".agent" / "tasks" / "shared-task-id.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    script = (
        "from pathlib import Path; import time; "
        f"started=Path({str(started)!r}); release=Path({str(release)!r}); "
        "started.write_text('started\\n', encoding='utf-8'); "
        "exec(\"while not release.exists():\\n time.sleep(0.05)\")"
    )
    task["resources"] = []
    task["memory_limit_mb"] = 256
    task["command_timeout"] = 30
    task["idle_timeout"] = 30
    task["task_timeout"] = 60
    task["steps"] = [
        {
            "name": "hold-control-repository-lease",
            "command": f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}",
            "timeout": 30,
        }
    ]
    task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    git(["add", ".agent/tasks/shared-task-id.json"], cwd=control)
    git(["commit", "-m", "Configure blocking control task"], cwd=control)
    git(["push", "origin", "agent-control"], cwd=control)


def remove_initial_task(item: dict[str, Path | str]) -> None:
    control = Path(item["control"])
    git(["rm", ".agent/tasks/shared-task-id.json"], cwd=control)
    git(["commit", "-m", "Start second repository idle"], cwd=control)
    git(["push", "origin", "agent-control"], cwd=control)


def queue_late_task(root: Path, item: dict[str, Path | str]) -> None:
    repository_id = str(item["id"])
    queue = root / f"{repository_id}-queue"
    remote = root / f"{repository_id}.git"
    git(["clone", "--branch", "agent-control", str(remote), str(queue)])
    configure_identity(queue)
    task = {
        "id": "late-task",
        "mode": "commands",
        "work_branch": "main",
        "allow_write": False,
        "resources": [],
        "memory_limit_mb": 256,
        "command_timeout": 30,
        "idle_timeout": 10,
        "task_timeout": 60,
        "steps": [
            {
                "name": "late-software-task",
                "command": "printf 'late-task-ok\\n'",
                "timeout": 30,
            }
        ],
    }
    task_path = queue / ".agent" / "tasks" / "late-task.json"
    task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    git(["add", ".agent/tasks/late-task.json"], cwd=queue)
    git(["commit", "-m", "Queue late software task"], cwd=queue)
    git(["push", "origin", "agent-control"], cwd=queue)


class ControlIdentifierHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.original_control = agentd.core.CONTROL
        agentd.core.CONTROL = Path(self.tmp.name) / "control"
        (agentd.core.CONTROL / ".agent" / "daemon" / "acks").mkdir(
            parents=True,
            exist_ok=True,
        )

    def tearDown(self) -> None:
        agentd.core.CONTROL = self.original_control
        self.tmp.cleanup()

    def test_control_id_validation_rejects_path_syntax(self) -> None:
        self.assertTrue(agentd.valid_control_id("status-1_ok.v2"))
        for value in (
            "",
            "../tasks/evil",
            "nested/id",
            "/absolute",
            "space id",
            "a" * 121,
        ):
            with self.subTest(value=value):
                self.assertFalse(agentd.valid_control_id(value))

    def test_publish_control_ack_rejects_traversal_before_publication(self) -> None:
        with mock.patch.object(agentd, "publish_control_json") as publish:
            with self.assertRaisesRegex(ValueError, "invalid daemon control id"):
                agentd.publish_control_ack("../tasks/evil", "status", "completed")
        publish.assert_not_called()

    def test_global_control_handler_rejects_invalid_id_before_ack_lookup(self) -> None:
        request = agentd.core.CONTROL / agentd.REMOTE_CONTROL_REQUEST
        request.parent.mkdir(parents=True, exist_ok=True)
        request.write_text(
            json.dumps({"id": "../tasks/evil", "action": "status"}),
            encoding="utf-8",
        )
        with mock.patch.object(agentd, "control_ack_published") as ack_lookup, mock.patch.object(
            agentd, "publish_control_ack"
        ) as publish:
            agentd.handle_control_request()
        ack_lookup.assert_not_called()
        publish.assert_not_called()

    def test_parallel_probe_rejects_invalid_id_before_ack_lookup(self) -> None:
        request = agentd.core.CONTROL / agentd.REMOTE_CONTROL_REQUEST
        request.parent.mkdir(parents=True, exist_ok=True)
        request.write_text(
            json.dumps({"id": "../tasks/evil", "action": "status"}),
            encoding="utf-8",
        )
        with mock.patch.object(agentd, "control_ack_published") as ack_lookup:
            result = parallel.pending_control_request_from_bound_checkout()
        self.assertIs(result, parallel.ControlProbeResult.CLEAR)
        ack_lookup.assert_not_called()


class DeferredControlAdmissionIntegrationTests(unittest.TestCase):
    def test_busy_control_repository_does_not_starve_unrelated_late_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            control_repo = create_repository_fixture(root, "control-repo")
            other_repo = create_repository_fixture(root, "other-repo")
            started = root / "control-started"
            release = root / "control-release"
            configure_blocking_control_task(
                control_repo,
                started=started,
                release=release,
            )
            remove_initial_task(other_repo)
            registry = write_registry(root, (control_repo, other_repo))
            _, env = test_environment(root)

            code = (
                "import sys; "
                "import agent_multirepo as serial; "
                "import agent_parallel as parallel; "
                "serial.POLL_SECONDS=0.1; "
                "serial.SUPERVISOR_CONTROL_POLL_SECONDS=0.1; "
                "parallel.ERROR_RETRY_SECONDS=0.1; "
                "parallel.REAP_INTERVAL_SECONDS=0.05; "
                "parallel.RESOURCE_RETRY_SECONDS=0.1; "
                f"sys.argv=['agent_parallel.py','--registry',{str(registry)!r},'--max-workers','2']; "
                "raise SystemExit(parallel.main())"
            )
            supervisor = subprocess.Popen(
                [sys.executable, "-c", code],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                wait_for_path(started)
                time.sleep(0.4)
                queue_late_task(root, other_repo)
                result_path = (
                    Path(other_repo["control"])
                    / ".agent"
                    / "results"
                    / "late-task.json"
                )
                wait_for_path(result_path, timeout=8.0)
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["status"], "done")
                self.assertIn("late-task-ok", payload["commands"][0]["output"])
                self.assertFalse(release.exists())
            except Exception as exc:
                output = ""
                if supervisor.stdout is not None:
                    with contextlib.suppress(Exception):
                        supervisor.terminate()
                        supervisor.wait(timeout=5)
                    output = supervisor.stdout.read()
                self.fail(f"{exc}\nsupervisor output:\n{output}")
            finally:
                release.touch(exist_ok=True)
                if supervisor.poll() is None:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(supervisor.pid, signal.SIGTERM)
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        supervisor.wait(timeout=10)
                if supervisor.poll() is None:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(supervisor.pid, signal.SIGKILL)
                    supervisor.wait(timeout=5)
                if supervisor.stdout is not None:
                    supervisor.stdout.close()


if __name__ == "__main__":
    unittest.main()
