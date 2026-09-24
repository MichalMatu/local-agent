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
    "docs/AUTONOMOUS_CHAT_LOOP.md",
    "docs/EMERGENCY_CONTROLS.md",
    "docs/GOLDEN_STANDARD.md",
    "docs/MULTI_REPOSITORY.md",
    "docs/OPERATIONS.md",
    "docs/SECURITY_MODEL.md",
    "docs/SESSION_BOOTSTRAP.md",
    "deploy/macos/README.md",
)
CURRENT_SCHEDULER_DOCS = (
    "AGENTS.md",
    "docs/GOLDEN_STANDARD.md",
    "docs/MULTI_REPOSITORY.md",
    "docs/OPERATIONS.md",
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

    def test_current_scheduler_docs_describe_final_behavior_not_unresolved_candidate_work(self) -> None:
        forbidden = (
            "candidate fix must",
            "The candidate fix must",
            "The v4.18.14 candidate is not production",
            "The current release candidate is v4.18.14",
            "After a validated v4.18.14 candidate is explicitly advanced to `main`",
        )
        for relative in CURRENT_SCHEDULER_DOCS:
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            for phrase in forbidden:
                with self.subTest(path=relative, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_bug_002_is_not_left_in_pre_release_candidate_state(self) -> None:
        backlog = (REPO_ROOT / "docs" / "BUG_BACKLOG.md").read_text(encoding="utf-8")
        section = backlog.split("## BUG-002", maxsplit=1)[1].split("\n---\n", maxsplit=1)[0]
        self.assertIn("**Status:** Fixed", section)
        self.assertNotIn("pending v4.18.14 merge/tag/live verification", section)
        self.assertNotIn("Until v4.18.14 is merged/tagged", section)

    def test_session_bootstrap_does_not_claim_preserved_paths_are_derived_from_current_ids(self) -> None:
        bootstrap = (REPO_ROOT / "docs" / "SESSION_BOOTSTRAP.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "All four current registry entries use the default non-legacy workspace layout derived from their repository ids",
            bootstrap,
        )
        self.assertIn("preserved physical workspace paths", bootstrap)

    def test_golden_standard_names_released_source_as_current_production(self) -> None:
        golden = (REPO_ROOT / "docs" / "GOLDEN_STANDARD.md").read_text(encoding="utf-8")
        self.assertIn(f"source release is `v{RELEASE_VERSION}`", golden)
        self.assertIn(f"current production release is `v{RELEASE_VERSION}`", golden)
        self.assertNotIn("is still a candidate on this branch", golden)

    def test_release_version_has_matching_release_notes_and_changelog_entry(self) -> None:
        notes = REPO_ROOT / "docs" / f"RELEASE_NOTES_V{RELEASE_VERSION}.md"
        self.assertTrue(notes.is_file(), f"missing release notes for {RELEASE_VERSION}")
        notes_text = notes.read_text(encoding="utf-8")
        self.assertTrue(notes_text.startswith(f"# Local Agent {RELEASE_VERSION}\n"))
        self.assertNotIn("must not be tagged/frozen until", notes_text)
        self.assertNotIn("A follow-up candidate adds", notes_text)
        changelog = (REPO_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## v{RELEASE_VERSION}\n", changelog)


if __name__ == "__main__":
    unittest.main()
