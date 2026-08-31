from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agent_parallel as parallel
import agentd
from agent_process import ExecutionLeaseBusy
from agent_repository import RepositoryContext


def repository(root: Path) -> RepositoryContext:
    return RepositoryContext(
        repository_id="control-repo",
        repository="owner/control-repo",
        control=root / "control",
        work=root / "work",
        checkpoints=root / "checkpoints",
    )


class ParallelControlProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.original_control = agentd.core.CONTROL
        agentd.core.CONTROL = self.root / "control"
        (agentd.core.CONTROL / ".agent" / "daemon" / "acks").mkdir(
            parents=True,
            exist_ok=True,
        )

    def tearDown(self) -> None:
        agentd.core.CONTROL = self.original_control
        self.tmp.cleanup()

    def request_path(self) -> Path:
        return agentd.core.CONTROL / agentd.REMOTE_CONTROL_REQUEST

    def test_missing_request_does_not_trigger_drain(self) -> None:
        self.assertIs(
            parallel.pending_control_request_from_bound_checkout(),
            parallel.ControlProbeResult.CLEAR,
        )

    def test_unacknowledged_request_triggers_drain(self) -> None:
        path = self.request_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"id": "restart-1", "action": "restart"}),
            encoding="utf-8",
        )
        with mock.patch.object(agentd, "control_ack_published", return_value=False):
            self.assertIs(
                parallel.pending_control_request_from_bound_checkout(),
                parallel.ControlProbeResult.PENDING,
            )

    def test_acknowledged_request_does_not_trigger_repeat_drain(self) -> None:
        path = self.request_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"id": "status-1", "action": "status"}),
            encoding="utf-8",
        )
        ack = (
            agentd.core.CONTROL
            / agentd.REMOTE_CONTROL_ACK_DIR
            / "status-1.json"
        )
        ack.write_text("{}\n", encoding="utf-8")
        with mock.patch.object(agentd, "control_ack_published", return_value=True):
            self.assertIs(
                parallel.pending_control_request_from_bound_checkout(),
                parallel.ControlProbeResult.CLEAR,
            )

    def test_malformed_request_is_not_allowed_to_force_drain(self) -> None:
        path = self.request_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="utf-8")
        with mock.patch.object(parallel, "log") as log:
            self.assertIs(
                parallel.pending_control_request_from_bound_checkout(),
                parallel.ControlProbeResult.CLEAR,
            )
        self.assertIn("invalid daemon control request", log.call_args.args[0])

    def test_ack_probe_failure_is_deferred_for_prompt_retry(self) -> None:
        path = self.request_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"id": "status-retry", "action": "status"}),
            encoding="utf-8",
        )
        with mock.patch.object(
            agentd, "control_ack_published", side_effect=RuntimeError("network down")
        ), mock.patch.object(parallel, "log"):
            self.assertIs(
                parallel.pending_control_request_from_bound_checkout(),
                parallel.ControlProbeResult.DEFERRED,
            )

    def test_probe_uses_only_control_repository_lease(self) -> None:
        repo = repository(self.root)
        with mock.patch.object(
            parallel.serial_worker,
            "repository_execution_lease",
            return_value=contextlib.nullcontext(),
        ) as lease, mock.patch.object(
            parallel.serial,
            "bind_supervisor_control",
        ), mock.patch.object(
            parallel.serial,
            "sync_control_quietly",
        ), mock.patch.object(
            parallel,
            "pending_control_request_from_bound_checkout",
            return_value=parallel.ControlProbeResult.PENDING,
        ):
            self.assertIs(
                parallel.probe_control_request(repo),
                parallel.ControlProbeResult.PENDING,
            )
        lease.assert_called_once_with(repo)

    def test_busy_control_repository_defers_probe_without_global_drain(self) -> None:
        repo = repository(self.root)

        @contextlib.contextmanager
        def busy_lease(_repository):
            raise ExecutionLeaseBusy("repo:control-repo")
            yield

        with mock.patch.object(
            parallel.serial_worker,
            "repository_execution_lease",
            side_effect=busy_lease,
        ):
            self.assertIs(
                parallel.probe_control_request(repo),
                parallel.ControlProbeResult.DEFERRED,
            )


if __name__ == "__main__":
    unittest.main()
