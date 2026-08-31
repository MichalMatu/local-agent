from __future__ import annotations

import unittest

import agent_parallel_worker as worker


class ParallelWorkerResourceTests(unittest.TestCase):
    def test_missing_resources_preserves_legacy_exclusive_behavior(self) -> None:
        self.assertEqual(worker.task_resources({"id": "a"}), ("machine",))

    def test_empty_resources_is_parallel_safe(self) -> None:
        self.assertEqual(worker.task_resources({"id": "a", "resources": []}), ())

    def test_named_resources_are_casefolded_deduplicated_and_sorted(self) -> None:
        task = {"id": "a", "resources": ["USB", "serial", "usb"]}
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


if __name__ == "__main__":
    unittest.main()
