from __future__ import annotations

import json
import unittest
from pathlib import Path

from local_agent.repository.binding import load_binding_catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_AGENT_BINDING = "2180d453-1357-4fbc-be1a-e1e5b8fbb10a"


class HostOpsRetirementTests(unittest.TestCase):
    def test_standalone_host_ops_is_not_an_execution_target(self) -> None:
        ids = {record.repository_id for record in load_binding_catalog()}
        self.assertNotIn("host-ops", ids)

    def test_local_agent_owns_absorbed_host_ops_execution(self) -> None:
        matches = [record for record in load_binding_catalog() if record.repository_id == "local-agent"]
        self.assertEqual(len(matches), 1)
        record = matches[0]
        self.assertEqual(record.repository, "MichalMatu/local-agent")
        self.assertEqual(record.agent_binding, LOCAL_AGENT_BINDING)
        self.assertTrue(record.execution_enabled)

    def test_bridge_runtime_example_has_no_standalone_host_ops_identity(self) -> None:
        runtime = json.loads(
            (REPO_ROOT / "chat_bridge" / "runtime.example.json").read_text(encoding="utf-8")
        )
        ids = {item["repository_id"] for item in runtime["agents"]}
        self.assertNotIn("host-ops", ids)
        self.assertIn("local-agent", ids)


if __name__ == "__main__":
    unittest.main()
