from __future__ import annotations

import unittest

import agent_parallel_worker as worker
from agent_version import RELEASE_VERSION
from local_agent.runtime.task_contract import MAX_MEMORY_LIMIT_MB, MAX_TASK_RESOURCES


class ParallelWorkerResourceTests(unittest.TestCase):
    def test_parallel_daemon_version_matches_release(self) -> None:
        self.assertEqual(worker.PARALLEL_DAEMON_VERSION, RELEASE_VERSION)

    def test_resources_must_be_declared_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "declared explicitly"):
            worker.task_resources({"id": "a"})

    def test_empty_resources_is_software_only_independent_of_memory_limit(self) -> None:
        self.assertEqual(worker.task_resources({"id": "a", "resources": []}), ())
        self.assertEqual(
            worker.task_resources(
                {"id": "a", "resources": [], "memory_limit_mb": 0}
            ),
            (),
        )
        self.assertEqual(
            worker.task_resources(
                {
                    "id": "a",
                    "resources": [],
                    "memory_limit_mb": MAX_MEMORY_LIMIT_MB,
                }
            ),
            (),
        )

    def test_named_resources_preserve_explicit_canonical_names(self) -> None:
        task = {
            "id": "a",
            "resources": ["board:growbox-s3", "serial:s3"],
            "memory_limit_mb": 2048,
        }
        self.assertEqual(
            worker.task_resources(task),
            ("board:growbox-s3", "serial:s3"),
        )

    def test_machine_resource_must_be_declared_alone(self) -> None:
        self.assertEqual(
            worker.task_resources({"id": "a", "resources": ["machine"]}),
            ("machine",),
        )
        with self.assertRaisesRegex(ValueError, "must be declared alone"):
            worker.task_resources(
                {"id": "a", "resources": ["machine", "board:zigbee-c6"]}
            )

    def test_malformed_resources_are_rejected(self) -> None:
        invalid = (
            {"id": "a", "resources": "usb"},
            {"id": "a", "resources": ["bad value"]},
            {"id": "a", "resources": ["USB"]},
            {"id": "a", "resources": [""]},
            {"id": "a", "resources": [" usb"]},
            {"id": "a", "resources": [1]},
        )
        for task in invalid:
            with self.subTest(task=task), self.assertRaises(ValueError):
                worker.task_resources(task)

    def test_duplicate_resources_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate resource"):
            worker.task_resources(
                {"id": "a", "resources": ["board:s3", "board:s3"]}
            )

    def test_resource_list_is_bounded(self) -> None:
        task = {
            "id": "a",
            "resources": [f"resource-{index}" for index in range(MAX_TASK_RESOURCES + 1)],
        }
        with self.assertRaisesRegex(ValueError, "resources exceeds"):
            worker.task_resources(task)


if __name__ == "__main__":
    unittest.main()
