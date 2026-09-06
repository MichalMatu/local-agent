from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import local_agent.foundation.storage as storage
import local_agent.repository.cleanup as cleanup
from local_agent.foundation.process import LEASE_FDS_ENV, RESOURCE_LEASE_FDS_ENV


class InterruptedRuntimeTaskRecoveryTests(unittest.TestCase):
    def test_interrupted_gc_task_deletion_is_restored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "storage-test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "storage@example.invalid"], cwd=repo, check=True)
            task = repo / ".agent" / "tasks" / "terminal.json"
            task.parent.mkdir(parents=True)
            task.write_text('{"id":"terminal"}\n', encoding="utf-8")
            subprocess.run(["git", "add", ".agent/tasks/terminal.json"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
            task.unlink()

            def process(args, cwd, **_kwargs):
                completed = subprocess.run(
                    args,
                    cwd=cwd,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                return {"exit_code": completed.returncode, "output": completed.stdout}

            core = mock.Mock()
            core.CONTROL = repo
            core.process.side_effect = process
            storage.recover_daemon_owned_control_changes(core)

            self.assertTrue(task.exists())
            self.assertEqual(task.read_text(encoding="utf-8"), '{"id":"terminal"}\n')
            status = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            )
            self.assertEqual(status.stdout, "")

    def test_modified_task_file_remains_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "storage-test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "storage@example.invalid"], cwd=repo, check=True)
            task = repo / ".agent" / "tasks" / "pending.json"
            task.parent.mkdir(parents=True)
            task.write_text('{"id":"pending"}\n', encoding="utf-8")
            subprocess.run(["git", "add", ".agent/tasks/pending.json"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
            task.write_text('{"id":"changed"}\n', encoding="utf-8")

            def process(args, cwd, **_kwargs):
                completed = subprocess.run(
                    args,
                    cwd=cwd,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                return {"exit_code": completed.returncode, "output": completed.stdout}

            core = mock.Mock()
            core.CONTROL = repo
            core.process.side_effect = process
            with self.assertRaisesRegex(RuntimeError, "unexpected local changes"):
                storage.recover_daemon_owned_control_changes(core)
            self.assertEqual(task.read_text(encoding="utf-8"), '{"id":"changed"}\n')

    def test_runtime_gc_drops_only_resource_lease_descriptors(self) -> None:
        core = SimpleNamespace(
            ENV={
                "PATH": "/usr/bin",
                LEASE_FDS_ENV: "7,8",
                RESOURCE_LEASE_FDS_ENV: "9,10",
            }
        )
        environment = cleanup._control_git_environment(core)
        self.assertIsNotNone(environment)
        assert environment is not None
        self.assertEqual(environment["PATH"], "/usr/bin")
        self.assertEqual(environment[LEASE_FDS_ENV], "7,8")
        self.assertNotIn(RESOURCE_LEASE_FDS_ENV, environment)


if __name__ == "__main__":
    unittest.main()
