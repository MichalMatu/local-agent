from __future__ import annotations

import unittest

import agent_runtime
from local_agent.runtime import task_contract


class RuntimeTaskContractModuleTests(unittest.TestCase):
    def test_public_contract_functions_are_compatibly_reexported(self) -> None:
        self.assertIs(agent_runtime.task_digest, task_contract.task_digest)
        self.assertIs(agent_runtime.validate_task, task_contract.validate_task)
        self.assertIs(agent_runtime.idle_timeout_for, task_contract.idle_timeout_for)
        self.assertIs(agent_runtime.task_timeout_for, task_contract.task_timeout_for)
        self.assertIs(agent_runtime.memory_limit_for, task_contract.memory_limit_for)

    def test_contract_limits_are_compatibly_reexported(self) -> None:
        self.assertEqual(agent_runtime.MAX_PATCH_BYTES, task_contract.MAX_PATCH_BYTES)
        self.assertEqual(agent_runtime.MAX_TASK_LIST_ITEMS, task_contract.MAX_TASK_LIST_ITEMS)
        self.assertEqual(agent_runtime.TASK_FINALIZATION_RESERVE, task_contract.TASK_FINALIZATION_RESERVE)

    def test_extracted_contract_validates_independently(self) -> None:
        task = {"id": "contract-smoke", "resources": [], "commands": ["true"], "command_timeout": 60, "task_timeout": 180}
        task_contract.validate_task(task)
        self.assertEqual(task_contract.task_timeout_for(task), 180)
        self.assertEqual(task_contract.task_digest(task), agent_runtime.task_digest(task))


if __name__ == "__main__":
    unittest.main()
