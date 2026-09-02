from __future__ import annotations

import unittest
from pathlib import Path

import agent_multirepo as multi
import agent_parallel as parallel
import agentd
from agent_repository import RepositoryContext
from local_agent.supervisor import control, policy


def repository(repository_id: str) -> RepositoryContext:
    root = Path("/tmp") / repository_id
    return RepositoryContext(
        repository_id=repository_id,
        repository=f"owner/{repository_id}",
        control=root / "control",
        work=root / "work",
        checkpoints=root / "checkpoints",
    )


class SupervisorModuleBoundaryTests(unittest.TestCase):
    def test_parallel_does_not_depend_on_serial_fallback_entrypoint(self) -> None:
        source = Path(parallel.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import agent_multirepo", source)
        self.assertNotIn("serial.", source)

    def test_serial_consumes_shared_policy_primitives(self) -> None:
        self.assertIs(multi.adaptive_poll_tier, policy.adaptive_poll_tier)
        self.assertIs(multi.interval_due, policy.interval_due)
        self.assertIs(multi.interval_remaining, policy.interval_remaining)
        self.assertIs(multi.ordered_repositories, policy.ordered_repositories)
        self.assertEqual(multi.WORKER_TURN_GRACE_SECONDS, policy.WORKER_TURN_GRACE_SECONDS)

    def test_shared_policy_is_deterministic_and_entrypoint_neutral(self) -> None:
        self.assertEqual(policy.adaptive_poll_tier(None, 100.0), ("idle", 15.0))
        self.assertEqual(policy.adaptive_poll_tier(100.0, 101.0), ("hot", 2.0))
        items = [repository("a"), repository("b"), repository("c")]
        self.assertEqual(
            [item.repository_id for item in policy.ordered_repositories(items, "a")],
            ["b", "c", "a"],
        )

    def test_control_binding_requires_explicit_daemon_version(self) -> None:
        target = repository("control")
        original_control = agentd.core.CONTROL
        original_branch = agentd.core.CONTROL_BRANCH
        original_version = agentd.DAEMON_VERSION
        try:
            control.bind_supervisor_control(target, daemon_version="test-version")
            self.assertEqual(agentd.core.CONTROL, target.control)
            self.assertEqual(agentd.core.CONTROL_BRANCH, target.control_branch)
            self.assertEqual(agentd.DAEMON_VERSION, "test-version")
        finally:
            agentd.core.CONTROL = original_control
            agentd.core.CONTROL_BRANCH = original_branch
            agentd.DAEMON_VERSION = original_version


if __name__ == "__main__":
    unittest.main()
