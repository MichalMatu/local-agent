from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from local_agent.foundation import storage
from local_agent.operator import remote


class GitNetworkResilienceTests(unittest.TestCase):
    def test_network_wrapper_caps_legacy_timeout(self) -> None:
        process = mock.Mock(return_value={"exit_code": 0, "output": ""})
        core = SimpleNamespace(process=process, log=mock.Mock())

        result = storage.run_git_with_network_retry(
            core,
            ["git", "fetch", "origin"],
            Path("/tmp/control"),
            timeout=180,
        )

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(
            process.call_args.kwargs["timeout"],
            storage.GIT_NETWORK_ATTEMPT_TIMEOUT_MAX,
        )

    def test_circuit_breaker_suppresses_repeated_network_probe(self) -> None:
        process = mock.Mock(
            side_effect=[
                {"exit_code": 124, "output": "", "timed_out": True},
                {"exit_code": 0, "output": ""},
            ]
        )
        core = SimpleNamespace(process=process, log=mock.Mock())
        breaker = storage.GitNetworkCircuitBreaker(open_seconds=30.0)

        with mock.patch.object(storage.time, "monotonic", side_effect=[100.0, 100.0]):
            failed = storage.run_git_with_network_retry(
                core,
                ["git", "pull", "origin", "agent-control"],
                Path("/tmp/control"),
                retry_delays=(),
                circuit_breaker=breaker,
            )

        self.assertEqual(failed["exit_code"], 124)
        self.assertEqual(breaker.open_until, 130.0)
        self.assertEqual(process.call_count, 1)

        with mock.patch.object(storage.time, "monotonic", return_value=110.0):
            suppressed = storage.run_git_with_network_retry(
                core,
                ["git", "pull", "origin", "agent-control"],
                Path("/tmp/control"),
                circuit_breaker=breaker,
            )

        self.assertEqual(suppressed["exit_code"], 75)
        self.assertTrue(suppressed["network_circuit_open"])
        self.assertEqual(process.call_count, 1)

        with mock.patch.object(storage.time, "monotonic", return_value=131.0):
            recovered = storage.run_git_with_network_retry(
                core,
                ["git", "pull", "origin", "agent-control"],
                Path("/tmp/control"),
                circuit_breaker=breaker,
            )

        self.assertEqual(recovered["exit_code"], 0)
        self.assertEqual(breaker.open_until, 0.0)
        self.assertEqual(process.call_count, 2)

    def test_remote_operator_transport_failure_opens_probe_backoff(self) -> None:
        state = remote.RemoteOperatorState(
            last_ref="a" * 40,
            desired_state="enabled",
            request_id="enable-1",
        )
        repository = Path("/tmp/local-agent")

        with mock.patch.object(
            remote,
            "_remote_ref",
            side_effect=RuntimeError("network down"),
        ) as probe:
            first = remote.poll_remote_operator(
                state,
                self_repo=repository,
                now=10.0,
            )
            second = remote.poll_remote_operator(
                state,
                self_repo=repository,
                now=14.0,
            )

        self.assertEqual(first, "enabled")
        self.assertEqual(second, "enabled")
        self.assertEqual(probe.call_count, 1)
        self.assertEqual(state.consecutive_transport_failures, 1)
        self.assertEqual(state.retry_not_before, 15.0)

    def test_remote_operator_success_closes_probe_backoff(self) -> None:
        state = remote.RemoteOperatorState(
            last_poll_at=10.0,
            last_ref="a" * 40,
            desired_state="enabled",
            request_id="enable-1",
            consecutive_transport_failures=2,
            retry_not_before=20.0,
        )

        with mock.patch.object(remote, "_remote_ref", return_value="a" * 40):
            result = remote.poll_remote_operator(
                state,
                self_repo=Path("/tmp/local-agent"),
                now=20.0,
            )

        self.assertEqual(result, "enabled")
        self.assertEqual(state.consecutive_transport_failures, 0)
        self.assertEqual(state.retry_not_before, 0.0)


if __name__ == "__main__":
    unittest.main()
