from __future__ import annotations

import json
import unittest
from pathlib import Path

from local_agent.repository.binding import load_binding_catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
WOLF_UE5_BINDING = "82180c40-c17b-4ddb-b17f-d90f7b80436a"


class WolfUe5OnboardingTests(unittest.TestCase):
    def test_wolf_ue5_is_execution_enabled_in_canonical_catalog(self) -> None:
        matches = [
            record for record in load_binding_catalog() if record.repository_id == "wolf-ue5"
        ]

        self.assertEqual(len(matches), 1)
        record = matches[0]
        self.assertEqual(record.repository, "MichalMatu/wolf-ue5")
        self.assertEqual(record.agent_binding, WOLF_UE5_BINDING)
        self.assertTrue(record.execution_enabled)

    def test_bridge_runtime_example_matches_wolf_ue5_canonical_identity(self) -> None:
        runtime = json.loads(
            (REPO_ROOT / "chat_bridge" / "runtime.example.json").read_text(encoding="utf-8")
        )
        matches = [
            item for item in runtime["agents"] if item.get("repository_id") == "wolf-ue5"
        ]

        self.assertEqual(
            matches,
            [
                {
                    "repository_id": "wolf-ue5",
                    "repository": "MichalMatu/wolf-ue5",
                    "agent_binding": WOLF_UE5_BINDING,
                    "execution_enabled": True,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
