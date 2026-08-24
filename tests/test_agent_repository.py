from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_repository import (
    DEFAULT_REPOSITORY,
    DEFAULT_REPOSITORY_ID,
    load_repository_registry,
)


class RepositoryRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        self.registry = self.home / "repositories.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, repositories: list[dict]) -> None:
        self.registry.write_text(
            json.dumps({"version": 1, "repositories": repositories}),
            encoding="utf-8",
        )

    def test_missing_registry_preserves_legacy_litegraph_workspace(self) -> None:
        repositories = load_repository_registry(home=self.home, path=self.registry)
        self.assertEqual(len(repositories), 1)
        repository = repositories[0]
        self.assertEqual(repository.repository_id, DEFAULT_REPOSITORY_ID)
        self.assertEqual(repository.repository, DEFAULT_REPOSITORY)
        self.assertEqual(repository.control, self.home / "agent-workspace" / "control")
        self.assertEqual(repository.work, self.home / "agent-workspace" / "work")
        self.assertEqual(
            repository.checkpoints,
            self.home / "agent-workspace" / "checkpoints",
        )

    def test_multiple_repositories_receive_isolated_default_workspaces(self) -> None:
        self.write(
            [
                {
                    "id": "litegraph",
                    "repository": "MichalMatu/esp32s3_LiteGraph",
                    "legacy_workspace": True,
                },
                {"id": "photomaps", "repository": "MichalMatu/PhotoMaps"},
                {"id": "wreckscanner", "repository": "MichalMatu/WreckScanner"},
            ]
        )
        repositories = load_repository_registry(home=self.home, path=self.registry)
        self.assertEqual([item.repository_id for item in repositories], ["litegraph", "photomaps", "wreckscanner"])
        self.assertEqual(repositories[0].work, self.home / "agent-workspace" / "work")
        self.assertEqual(
            repositories[1].work,
            self.home / "agent-workspace" / "repos" / "photomaps" / "work",
        )
        self.assertEqual(
            repositories[2].control,
            self.home / "agent-workspace" / "repos" / "wreckscanner" / "control",
        )
        all_paths = {
            path
            for repository in repositories
            for path in (repository.control, repository.work, repository.checkpoints)
        }
        self.assertEqual(len(all_paths), 9)

    def test_disabled_repository_is_ignored(self) -> None:
        self.write(
            [
                {"id": "one", "repository": "owner/one"},
                {"id": "two", "repository": "owner/two", "enabled": False},
            ]
        )
        repositories = load_repository_registry(home=self.home, path=self.registry)
        self.assertEqual([item.repository_id for item in repositories], ["one"])

    def test_duplicate_repository_id_is_rejected(self) -> None:
        self.write(
            [
                {"id": "same", "repository": "owner/one"},
                {"id": "same", "repository": "owner/two"},
            ]
        )
        with self.assertRaisesRegex(ValueError, "duplicate repository id"):
            load_repository_registry(home=self.home, path=self.registry)

    def test_workspace_collision_is_rejected(self) -> None:
        shared = str(self.home / "shared")
        self.write(
            [
                {"id": "one", "repository": "owner/one", "work_dir": shared},
                {"id": "two", "repository": "owner/two", "control_dir": shared},
            ]
        )
        with self.assertRaisesRegex(ValueError, "workspace path collision"):
            load_repository_registry(home=self.home, path=self.registry)

    def test_normalized_and_nested_workspace_collisions_are_rejected(self) -> None:
        shared = self.home / "shared"
        self.write(
            [
                {"id": "one", "repository": "owner/one", "work_dir": str(shared)},
                {
                    "id": "two",
                    "repository": "owner/two",
                    "control_dir": str(self.home / "parent" / ".." / "shared"),
                },
            ]
        )
        with self.assertRaisesRegex(ValueError, "workspace path collision"):
            load_repository_registry(home=self.home, path=self.registry)

        self.write(
            [
                {
                    "id": "nested",
                    "repository": "owner/nested",
                    "work_dir": str(shared),
                    "checkpoints_dir": str(shared / "checkpoints"),
                }
            ]
        )
        with self.assertRaisesRegex(ValueError, "workspace path collision"):
            load_repository_registry(home=self.home, path=self.registry)

    def test_registry_booleans_require_exact_json_boolean_type(self) -> None:
        for field in ("enabled", "legacy_workspace"):
            with self.subTest(field=field):
                self.write(
                    [{"id": "one", "repository": "owner/one", field: "false"}]
                )
                with self.assertRaisesRegex(ValueError, "must be a boolean"):
                    load_repository_registry(home=self.home, path=self.registry)

    def test_invalid_repository_and_relative_paths_are_rejected(self) -> None:
        self.write([{"id": "bad/id", "repository": "owner/repo"}])
        with self.assertRaisesRegex(ValueError, "invalid repository id"):
            load_repository_registry(home=self.home, path=self.registry)

        self.write([{"id": "ok", "repository": "not-a-repository"}])
        with self.assertRaisesRegex(ValueError, "invalid repository name"):
            load_repository_registry(home=self.home, path=self.registry)

        self.write(
            [
                {
                    "id": "ok",
                    "repository": "owner/repo",
                    "work_dir": "relative/work",
                }
            ]
        )
        with self.assertRaisesRegex(ValueError, "must be absolute"):
            load_repository_registry(home=self.home, path=self.registry)


if __name__ == "__main__":
    unittest.main()
