from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from local_agent.version import RELEASE_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]


class CurrentDocumentationContractTests(unittest.TestCase):
    def test_architecture_document_names_current_modules(self) -> None:
        architecture = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        for token in (
            "local_agent.supervisor.scheduling",
            "local_agent.supervisor.orchestrator",
            "local_agent.repository.binding",
            "local_agent.mcp",
        ):
            self.assertIn(token, architecture)

    def test_operations_document_names_current_entrypoints(self) -> None:
        operations = (REPO_ROOT / "docs" / "OPERATIONS.md").read_text(encoding="utf-8")
        for token in (
            "agent_parallel.py",
            "agent_multirepo.py",
            "local_agent.operator.local",
            "local_agent.repository.admin",
        ):
            self.assertIn(token, operations)

    def test_security_document_names_current_safety_boundaries(self) -> None:
        security = (REPO_ROOT / "docs" / "SECURITY_MODEL.md").read_text(encoding="utf-8")
        for token in (
            "agent_binding",
            "resources",
            "memory_limit_mb",
            "MCP",
        ):
            self.assertIn(token, security)

    def test_multi_repository_document_names_parallel_contract(self) -> None:
        multirepo = (REPO_ROOT / "docs" / "MULTI_REPOSITORY.md").read_text(encoding="utf-8")
        for token in (
            "max-workers 4",
            "resources",
            "agent_binding",
            "operator-control",
        ):
            self.assertIn(token, multirepo)

    def test_docs_index_points_to_current_contracts(self) -> None:
        docs_index = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        for token in (
            "OPERATIONS.md",
            "ARCHITECTURE.md",
            "SECURITY_MODEL.md",
            "MULTI_REPOSITORY.md",
            "GOLDEN_STANDARD.md",
            "AUTONOMOUS_CHAT_LOOP.md",
            "HOST_OPS_MULTIREPO.md",
            "CHATGPT_DOM_CONTRACT.md",
        ):
            self.assertIn(token, docs_index)

    def test_root_readme_points_to_current_docs_index(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/README.md", readme)

    def test_autonomous_loop_documents_current_pacing_and_controls(self) -> None:
        autonomous = (REPO_ROOT / "docs" / "AUTONOMOUS_CHAT_LOOP.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("conversation_controls", autonomous)
        self.assertIn("control_generation", autonomous)
        self.assertIn("GitHub", autonomous)
        self.assertIn("PAUSE", autonomous)
        self.assertIn("RESUME", autonomous)
        self.assertIn("NEXT", autonomous)
        self.assertIn("INTERVAL", autonomous)
        self.assertIn("Master", autonomous)
        self.assertIn("two minutes", autonomous)
        self.assertIn("5-10 minutes", autonomous)
        self.assertIn("cancel", autonomous.lower())

    def test_host_ops_multirepo_scope_matches_catalog_and_runtime(self) -> None:
        catalog_path = REPO_ROOT / "config" / "agent_bindings.json"
        runtime_path = REPO_ROOT / "chat_bridge" / "runtime.example.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        catalog_host_ops = next(item for item in catalog["agents"] if item["id"] == "host-ops")
        runtime_host_ops = next(
            item for item in runtime["agents"] if item["repository_id"] == "host-ops"
        )
        self.assertEqual(catalog_host_ops["planner_scope"], "multirepo")
        self.assertEqual(runtime_host_ops["planner_scope"], "multirepo")
        for relative in (
            "AGENTS.md",
            "docs/AUTONOMOUS_CHAT_LOOP.md",
            "docs/GOLDEN_STANDARD.md",
            "docs/HOST_OPS_MULTIREPO.md",
        ):
            with self.subTest(path=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("host-ops", text)
                self.assertIn("multirepo", text)

    def test_golden_standard_release_state_matches_source_version(self) -> None:
        golden = (REPO_ROOT / "docs" / "GOLDEN_STANDARD.md").read_text(encoding="utf-8")
        released_match = re.search(
            r"current source and production release is `v([^`]+)`",
            golden,
        )
        if released_match is not None:
            self.assertEqual(released_match.group(1), RELEASE_VERSION)
            self.assertNotIn(
                f"deployed production release remains `v{RELEASE_VERSION}` until the explicit release decision advances `main`",
                golden,
            )
            self.assertNotIn(
                "Candidate source must not be described as current production before the explicit release decision advances `main`.",
                golden,
            )
        else:
            source_match = re.search(
                r"(?:source release|base source release marker) is `v([^`]+)`",
                golden,
            )
            production_match = re.search(r"current production release is `v([^`]+)`", golden)
            self.assertIsNotNone(source_match, "missing source release declaration")
            self.assertIsNotNone(production_match, "missing production release declaration")
            assert source_match is not None
            assert production_match is not None

            source_release = source_match.group(1)
            production_release = production_match.group(1)
            self.assertEqual(source_release, RELEASE_VERSION)

            if production_release != source_release:
                self.assertTrue(
                    f"The {source_release} candidate" in golden
                    or f"The {source_release} base candidate" in golden
                )
                self.assertIn(
                    f"deployed production release remains `v{production_release}` until the explicit release decision advances `main`",
                    golden,
                )
                self.assertIn(
                    "Candidate source must not be described as current production before the explicit release decision advances `main`.",
                    golden,
                )

        self.assertNotIn("is still a candidate on this branch", golden)

    def test_release_version_has_matching_release_notes_and_changelog_entry(self) -> None:
        notes = REPO_ROOT / "docs" / f"RELEASE_NOTES_V{RELEASE_VERSION}.md"
        self.assertTrue(notes.exists(), f"missing release notes for {RELEASE_VERSION}")
        changelog = (REPO_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## v{RELEASE_VERSION}", changelog)


if __name__ == "__main__":
    unittest.main()
