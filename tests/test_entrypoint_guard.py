from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agent_entrypoint
import agent_operator
import agent_remote_operator
from agent_repository import RepositoryContext


class RemoteOperatorControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state_dir = root / "state"
        self.disabled_path = self.state_dir / "disabled.json"
        self.state_patch = mock.patch.object(agent_operator, "STATE_DIR", self.state_dir)
        self.path_patch = mock.patch.object(agent_operator, "DISABLED_PATH", self.disabled_path)
        self.state_patch.start()
        self.path_patch.start()

    def tearDown(self) -> None:
        self.path_patch.stop()
        self.state_patch.stop()
        self.tmp.cleanup()

    def test_remote_disabled_persists_local_marker(self) -> None:
        state = agent_remote_operator.RemoteOperatorState()
        payload = {
            "version": 1,
            "desired_state": "disabled",
            "request_id": "stop-1",
        }
        with mock.patch.object(
            agent_remote_operator, "_remote_ref", return_value="a" * 40
        ), mock.patch.object(
            agent_remote_operator, "_load_remote_payload", return_value=payload
        ):
            desired = agent_remote_operator.poll_remote_operator(
                state,
                self_repo=Path("/tmp/self"),
                force=True,
            )

        self.assertEqual(desired, "disabled")
        self.assertTrue(agent_operator.is_disabled())
        marker = json.loads(self.disabled_path.read_text(encoding="utf-8"))
        self.assertEqual(marker["control_id"], "stop-1")
        self.assertEqual(marker["reason"], "remote_operator_control")

    def test_remote_enabled_never_clears_local_disable(self) -> None:
        agent_operator.disable_agent(reason="manual")
        state = agent_remote_operator.RemoteOperatorState()
        payload = {
            "version": 1,
            "desired_state": "enabled",
            "request_id": "resume-intent-1",
        }
        with mock.patch.object(
            agent_remote_operator, "_remote_ref", return_value="b" * 40
        ), mock.patch.object(
            agent_remote_operator, "_load_remote_payload", return_value=payload
        ):
            desired = agent_remote_operator.poll_remote_operator(
                state,
                self_repo=Path("/tmp/self"),
                force=True,
            )

        self.assertEqual(desired, "enabled")
        self.assertTrue(agent_operator.is_disabled())

    def test_cached_remote_disable_reasserts_deleted_marker_without_network_poll(self) -> None:
        state = agent_remote_operator.RemoteOperatorState(
            last_poll_at=10.0,
            last_ref="c" * 40,
            desired_state="disabled",
            request_id="stop-cached",
        )
        with mock.patch.object(agent_remote_operator, "_remote_ref") as remote_ref:
            desired = agent_remote_operator.poll_remote_operator(
                state,
                self_repo=Path("/tmp/self"),
                now=10.5,
            )
        remote_ref.assert_not_called()
        self.assertEqual(desired, "disabled")
        self.assertTrue(agent_operator.is_disabled())


class RuntimeResetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state_dir = root / "state"
        self.disabled_path = self.state_dir / "disabled.json"
        self.registry = root / "repositories.json"
        self.registry.write_text(
            json.dumps(
                {
                    "version": 1,
                    "repositories": [
                        {
                            "id": "project-a",
                            "repository": "owner/project-a",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.home_patch = mock.patch("pathlib.Path.home", return_value=root)
        self.state_patch = mock.patch.object(agent_operator, "STATE_DIR", self.state_dir)
        self.path_patch = mock.patch.object(agent_operator, "DISABLED_PATH", self.disabled_path)
        self.home_patch.start()
        self.state_patch.start()
        self.path_patch.start()

    def tearDown(self) -> None:
        self.path_patch.stop()
        self.state_patch.stop()
        self.home_patch.stop()
        self.tmp.cleanup()

    def test_runtime_reset_requires_disabled_state(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires Local Agent to be disabled"):
            agent_operator.reset_runtime_state(registry_path=self.registry)

    def test_runtime_reset_removes_repository_legacy_and_global_status(self) -> None:
        agent_operator.disable_agent(reason="test-reset")
        repository_state = self.state_dir / "repositories" / "project-a"
        for directory in ("claims", "corrupt-claims", "runs", "result-spool"):
            target = repository_state / directory
            target.mkdir(parents=True, exist_ok=True)
            (target / "old.json").write_text("{}", encoding="utf-8")
        (repository_state / "status.json").write_text("{}", encoding="utf-8")
        legacy_claims = self.state_dir / "claims"
        legacy_claims.mkdir(parents=True, exist_ok=True)
        (legacy_claims / "old.json").write_text("{}", encoding="utf-8")
        global_status = self.state_dir / "status.json"
        global_status.write_text('{"state":"disabled","pid":9548}', encoding="utf-8")

        result = agent_operator.reset_runtime_state(registry_path=self.registry)

        self.assertTrue(result["reset"])
        self.assertEqual(result["repository_ids"], ["project-a"])
        self.assertFalse((repository_state / "status.json").exists())
        self.assertEqual(list((repository_state / "claims").iterdir()), [])
        self.assertEqual(list(legacy_claims.iterdir()), [])
        self.assertFalse(global_status.exists())
        self.assertTrue(agent_operator.is_disabled())


class GuardedEntrypointTests(unittest.TestCase):
    def test_prepare_removes_generated_bytecode_and_provisions_missing_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repository = RepositoryContext(
                repository_id="project-a",
                repository="owner/project-a",
                control=root / "control",
                work=root / "work",
                checkpoints=root / "checkpoints",
            )
            (repository.control / ".git").mkdir(parents=True)
            pycache = repository.control / ".agent" / "patches" / "__pycache__"
            pycache.mkdir(parents=True)
            (pycache / "generated.pyc").write_bytes(b"bytecode")

            with mock.patch.object(agent_entrypoint, "provision_repository") as provision:
                agent_entrypoint.prepare_repositories([repository])

            provision.assert_called_once_with(repository)
            self.assertFalse(pycache.exists())

    def test_start_supervisor_disables_python_bytecode_writes(self) -> None:
        args = argparse.Namespace(registry=Path("/tmp/registry.json"), max_workers=2)
        fake = mock.Mock(pid=1234)
        with mock.patch.object(agent_entrypoint.subprocess, "Popen", return_value=fake) as popen:
            result = agent_entrypoint.start_supervisor(args)
        self.assertIs(result, fake)
        env = popen.call_args.kwargs["env"]
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertTrue(popen.call_args.kwargs["start_new_session"])


if __name__ == "__main__":
    unittest.main()
