from __future__ import annotations

import unittest
from pathlib import Path

from local_agent.version import RELEASE_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_OPERATIONAL_DOCS = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "docs/ARCHITECTURE.md",
    "docs/GOLDEN_STANDARD.md",
    "docs/MULTI_REPOSITORY.md",
    "docs/OPERATIONS.md",
    "docs/SESSION_BOOTSTRAP.md",
    "deploy/macos/README.md",
)


class CurrentDocumentationContractTests(unittest.TestCase):
    def test_current_operational_docs_do_not_restore_obsolete_two_worker_commands(self) -> None:
        for relative in CURRENT_OPERATIONAL_DOCS:
            with self.subTest(path=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertNotIn("--max-workers 2", text)

    def test_current_operational_docs_do_not_claim_obsolete_three_worker_cap(self) -> None:
        forbidden = (
            "hard cap remains three",
            "hard cap: `3`",
            "hard-caps the value at three",
        )
        for relative in CURRENT_OPERATIONAL_DOCS:
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            for phrase in forbidden:
                with self.subTest(path=relative, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_release_version_has_matching_release_notes_and_changelog_entry(self) -> None:
        notes = REPO_ROOT / "docs" / f"RELEASE_NOTES_V{RELEASE_VERSION}.md"
        self.assertTrue(notes.is_file(), f"missing release notes for {RELEASE_VERSION}")
        self.assertTrue(
            notes.read_text(encoding="utf-8").startswith(
                f"# Local Agent {RELEASE_VERSION}\n"
            )
        )
        changelog = (REPO_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## v{RELEASE_VERSION}\n", changelog)


if __name__ == "__main__":
    unittest.main()
