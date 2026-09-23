from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CF = ROOT / "docs" / "conversation_fabric"


class ConversationFabricTreeHygieneTests(unittest.TestCase):
    def test_donor_snapshots_are_not_in_active_tree(self) -> None:
        self.assertFalse(
            (ROOT / "archive" / "donors").exists(),
            "historical donor repo snapshots must stay in Git history, not the active tree",
        )

    def test_canonical_conversation_fabric_docs_exist(self) -> None:
        self.assertTrue((CF / "README.md").is_file())
        self.assertTrue((CF / "UNIFIED_DEVELOPMENT_DIRECTION.md").is_file())
        self.assertTrue((CF / "BRANCH_CONSOLIDATION.md").is_file())

    def test_superseded_plans_live_under_history(self) -> None:
        expected = (
            "HANDOFF_NEXT_CHAT.md",
            "IMPLEMENTATION_PLAN.md",
            "PREIMPLEMENTATION_REAUDIT.md",
            "SOURCE_ASSET_MAP.md",
            "SUPERCHAT_ARCHITECTURE.md",
            "CONSOLIDATED_DEVELOPMENT_ROADMAP.md",
        )
        history = CF / "history"
        for name in expected:
            self.assertTrue((history / name).is_file(), f"missing historical design evidence: {name}")
            self.assertFalse((CF / name).exists(), f"superseded plan must not look canonical: {name}")
        self.assertFalse(
            (ROOT / "docs" / "CONSOLIDATED_DEVELOPMENT_ROADMAP.md").exists(),
            "superseded roadmap must not remain at the top-level docs path",
        )

    def test_current_direction_does_not_point_work_to_deleted_branches(self) -> None:
        text = (CF / "UNIFIED_DEVELOPMENT_DIRECTION.md").read_text(encoding="utf-8")
        self.assertIn("develop/conversation-fabric", text)
        for prefix in ("feature/", "work/", "maintenance/", "plan/"):
            self.assertNotIn(
                f"Canonical development branch: `{prefix}",
                text,
                "current direction must not designate a deleted donor branch as canonical",
            )


if __name__ == "__main__":
    unittest.main()
