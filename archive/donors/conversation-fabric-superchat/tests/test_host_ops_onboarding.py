from __future__ import annotations

import json
import unittest
from pathlib import Path

from local_agent.repository.binding import load_binding_catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
HOST_OPS_BINDING = "16d688b6-b0ef-4905-a5bd-24e59c99cfb4"


class HostOpsOnboardingTests(unittest.TestCase):
    def test_host_ops_is_execution_enabled_in_canonical_catalog(self) -> None:
        matches = [record for record in load_binding_catalog() if record.repository_id == "host-ops"]

        self.assertEqual(len(matches), 1)
        record = matches[0]
        self.assertEqual(record.repository, "MichalMatu/host-ops")
        self.assertEqual(record.agent_binding, HOST_OPS_BINDING)
        self.assertTrue(record.execution_enabled)

    def test_bridge_runtime_example_matches_host_ops_canonical_identity(self) -> None:
        runtime = json.loads(
            (REPO_ROOT / "chat_bridge" / "runtime.example.json").read_text(encoding="utf-8")
        )
        matches = [
            item for item in runtime["agents"] if item.get("repository_id") == "host-ops"
        ]

        self.assertEqual(
            matches,
            [
                {
                    "repository_id": "host-ops",
                    "repository": "MichalMatu/host-ops",
                    "agent_binding": HOST_OPS_BINDING,
                    "execution_enabled": True,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
