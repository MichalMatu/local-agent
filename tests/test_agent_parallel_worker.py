from __future__ import annotations

import unittest

import agent_parallel_worker as worker
from agent_version import RELEASE_VERSION


class ParallelWorkerResourceTests(unittest.TestCase):
    def test_parallel_daemon_version_matches_release(self) -> None:
        self.assertEqual(worker.PARALLEL_DAEMON_VERSION, RELEASE_VERSION)

    def test_missing_resources_preserves_legacy_exclusive_behavior(self) -> None:
        self.assertEqual(worker.task_resources({"id": "a"}), ("machine",))

    def test_empty_resources_requires_bounded_parallel_memory(self) -> None:
        self.assertEqual(
            worker.task_resources(
                {"id": "a", "resources": [], "memory_limit_mb": 256}
            ),
            (),
        )
        self.assertEqual(
            worker.task_resources({"id": "a", "resources": []}),
            ("machine",),
        )
        self.assertEqual(
            worker.task_resources(
                {"id": "a", "resources": [], "memory_limit_mb": 0}
            ),
            ("machine",),
        )
        self.assertEqual(
            worker.task_resources(
                {
                    "id": "a",
                    "resources": [],
                    "memory_limit_mb": worker.MAX_PARALLEL_TASK_MEMORY_MB + 1,
                }
            ),
            ("machine",),
        )

    def test_named_resources_are_casefolded_deduplicated_and_sorted(self) -> None:
        task = {
            "id": "a",
            "resources": ["USB", "serial", "usb"],
            "memory_limit_mb": 256,
        }
        self.assertEqual(worker.task_resources(task), ("serial", "usb"))

    def test_machine_resource_collapses_to_full_exclusive_mode(self) -> None:
        task = {"id": "a", "resources": ["usb", "machine"]}
        self.assertEqual(worker.task_resources(task), ("machine",))

    def test_malformed_resources_fall_back_to_exclusive_mode(self) -> None:
        self.assertEqual(
            worker.task_resources({"id": "a", "resources": "usb"}),
            ("machine",),
        )
        self.assertEqual(
            worker.task_resources({"id": "a", "resources": ["bad value"]}),
            ("machine",),
        )

    def test_resource_list_is_bounded(self) -> None:
        task = {
            "id": "a",
            "resources": [f"resource-{index}" for index in range(20)],
            "memory_limit_mb": 256,
        }
        self.assertEqual(worker.task_resources(task), ("machine",))


if __name__ == "__main__":
    unittest.main()
