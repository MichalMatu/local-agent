from __future__ import annotations

import json
import unittest
from pathlib import Path

from local_agent.repository.binding import load_binding_catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
HARDWARE_LAB_BINDING = "fa3dc1d7-5ee2-4b59-841c-e41918610df1"


class HardwareLabOnboardingTests(unittest.TestCase):
    def test_hardware_lab_is_execution_enabled_in_canonical_catalog(self) -> None:
        matches = [
            record for record in load_binding_catalog() if record.repository_id == "hardware-lab"
        ]

        self.assertEqual(len(matches), 1)
        record = matches[0]
        self.assertEqual(record.repository, "MichalMatu/hardware-lab")
        self.assertEqual(record.agent_binding, HARDWARE_LAB_BINDING)
        self.assertTrue(record.execution_enabled)

    def test_bridge_runtime_example_matches_hardware_lab_canonical_identity(self) -> None:
        runtime = json.loads(
            (REPO_ROOT / "chat_bridge" / "runtime.example.json").read_text(encoding="utf-8")
        )
        matches = [
            item for item in runtime["agents"] if item.get("repository_id") == "hardware-lab"
        ]

        self.assertEqual(
            matches,
            [
                {
                    "repository_id": "hardware-lab",
                    "repository": "MichalMatu/hardware-lab",
                    "agent_binding": HARDWARE_LAB_BINDING,
                    "execution_enabled": True,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
