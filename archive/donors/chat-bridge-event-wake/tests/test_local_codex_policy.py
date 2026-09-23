from __future__ import annotations

import unittest

from local_agent.runtime.task_contract import validate_task


class LocalCodexPolicyTests(unittest.TestCase):
    def test_rejects_codex_in_legacy_commands(self) -> None:
        task = {
            "id": "reject-codex-command",
            "resources": [],
            "commands": ["codex exec --full-auto 'implement the change'"],
        }
        with self.assertRaisesRegex(ValueError, "may not invoke local Codex"):
            validate_task(task)

    def test_rejects_absolute_codex_path_in_structured_steps(self) -> None:
        task = {
            "id": "reject-codex-step",
            "resources": [],
            "steps": [
                {
                    "name": "delegate",
                    "command": "/opt/homebrew/bin/codex exec 'run tests and fix failures'",
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "may not invoke local Codex"):
            validate_task(task)

    def test_rejects_npx_codex_in_verify_commands(self) -> None:
        task = {
            "id": "reject-npx-codex",
            "resources": [],
            "verify_commands": ["npx @openai/codex exec 'review the result'"],
        }
        with self.assertRaisesRegex(ValueError, "may not invoke local Codex"):
            validate_task(task)


if __name__ == "__main__":
    unittest.main()
