from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import local_agent.supervisor.orchestrator as parallel
import local_agent.daemon.service as agentd
from local_agent.foundation.process import ExecutionLeaseBusy
from local_agent.repository.context import RepositoryContext


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
        self.status_path = self.root / "status.json"
        self.status_patch = mock.patch.object(agentd, "LOCAL_STATUS_PATH", self.status_path)
        self.status_patch.start()
        self.original_control = agentd.core.CONTROL
        agentd.core.CONTROL = self.root / "control"
        (agentd.core.CONTROL / ".agent" / "daemon" / "acks").mkdir(
            parents=True,
            exist_ok=True,
        )

    def tearDown(self) -> None:
        self.status_patch.stop()
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
            parallel.supervisor_control,
            "bind_supervisor_control",
        ), mock.patch.object(
            parallel.supervisor_control,
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

    def test_service_control_passes_parallel_status_metadata(self) -> None:
        repo = repository(self.root)
        with mock.patch.object(
            parallel, "supervisor_control_leases", return_value=contextlib.nullcontext()
        ), mock.patch.object(
            parallel.supervisor_control, "bind_supervisor_control"
        ), mock.patch.object(
            parallel.supervisor_control, "sync_control_quietly"
        ), mock.patch.object(
            agentd, "publish_daemon_status"
        ), mock.patch.object(
            agentd, "handle_control_request"
        ) as handle_control, mock.patch.object(
            agentd, "maybe_self_update"
        ):
            self.assertTrue(
                parallel.service_control(
                    [repo],
                    registry_path=None,
                    max_workers=2,
                    once=False,
                )
            )
        status_extra = handle_control.call_args.kwargs["status_extra"]
        self.assertEqual(status_extra["execution_model"], parallel.PARALLEL_EXECUTION_MODEL)
        self.assertEqual(status_extra["max_parallel_workers"], 2)
        self.assertEqual(status_extra["supervisor_control_repository"], repo.repository_id)

    def test_busy_control_repository_reports_lease_busy_without_immediate_global_drain(self) -> None:
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
                parallel.ControlProbeResult.LEASE_BUSY,
            )

    def test_control_activity_precedes_leases_and_clears_after_failure(self) -> None:
        repo = repository(self.root)
        for error in (ExecutionLeaseBusy("control-busy"), RuntimeError("sync failed")):
            with self.subTest(error=type(error).__name__):
                @contextlib.contextmanager
                def lease(_repositories):
                    status = json.loads(self.status_path.read_text(encoding="utf-8"))
                    self.assertEqual(status["state"], "running")
                    self.assertEqual(status["supervisor_control_repository"], repo.repository_id)
                    raise error
                    yield

                with mock.patch.object(
                    parallel, "supervisor_control_leases", side_effect=lease
                ), mock.patch.object(parallel, "log"), mock.patch.object(
                    parallel.agent_operator, "is_disabled", return_value=False
                ):
                    self.assertFalse(parallel.service_control(
                        [repo], registry_path=None, max_workers=2, once=False
                    ))
                status = json.loads(self.status_path.read_text(encoding="utf-8"))
                self.assertEqual(status["state"], "idle")
                self.assertNotIn("supervisor_control_repository", status)

    def test_control_service_preserves_disabled_status(self) -> None:
        with mock.patch.object(
            parallel, "supervisor_control_leases", side_effect=ExecutionLeaseBusy("busy")
        ), mock.patch.object(parallel.agent_operator, "is_disabled", return_value=True):
            self.assertFalse(parallel.service_control(
                [repository(self.root)], registry_path=None, max_workers=2, once=False
            ))
        status = json.loads(self.status_path.read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "disabled")
        self.assertNotIn("supervisor_control_repository", status)


if __name__ == "__main__":
    unittest.main()
