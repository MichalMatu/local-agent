from __future__ import annotations

import json
import unittest
from pathlib import Path

from local_agent.repository.binding import load_binding_catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_AGENT_BINDING = "2180d453-1357-4fbc-be1a-e1e5b8fbb10a"


class HostOpsRetirementTests(unittest.TestCase):
    def test_standalone_host_ops_is_not_a_canonical_execution_target(self) -> None:
        matches = [record for record in load_binding_catalog() if record.repository_id == "host-ops"]
        self.assertEqual(matches, [])

    def test_bridge_runtime_example_has_no_standalone_host_ops_identity(self) -> None:
        runtime = json.loads(
            (REPO_ROOT / "chat_bridge" / "runtime.example.json").read_text(encoding="utf-8")
        )
        matches = [
            item for item in runtime["agents"] if item.get("repository_id") == "host-ops"
        ]
        self.assertEqual(matches, [])

    def test_local_agent_remains_execution_enabled_for_absorbed_host_ops(self) -> None:
        matches = [record for record in load_binding_catalog() if record.repository_id == "local-agent"]
        self.assertEqual(len(matches), 1)
        record = matches[0]
        self.assertEqual(record.repository, "MichalMatu/local-agent")
        self.assertEqual(record.agent_binding, LOCAL_AGENT_BINDING)
        self.assertTrue(record.execution_enabled)


if __name__ == "__main__":
    unittest.main()
