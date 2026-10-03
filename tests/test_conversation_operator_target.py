from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from local_agent.development.operator_target import inspect_operator_target, resolve_operator_target


BINDING = "2db52048-57ea-4643-bf4b-1ea5c5c3fa86"
SHA = "a" * 40


class OperatorTargetTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path]:
        home = root / "home"
        control = root / "growclip-control"
        control.mkdir(parents=True)
        subprocess.run(["git", "init", str(control)], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(control),
                "remote",
                "add",
                "origin",
                "https://github.com/MichalMatu/growclip.git",
            ],
            check=True,
        )
        registry = root / "repositories.json"
        registry.write_text(
            json.dumps(
                {
                    "version": 1,
                    "repositories": [
                        {
                            "id": "growclip",
                            "repository": "MichalMatu/growclip",
                            "agent_binding": BINDING,
                            "control_dir": str(control),
                            "work_dir": str(root / "growclip-work"),
                            "checkpoints_dir": str(root / "growclip-checkpoints"),
                            "control_branch": "agent-control",
                            "default_branch": "main",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        catalog = root / "agent_bindings.json"
        catalog.write_text(
            json.dumps(
                {
                    "version": 1,
                    "agents": [
                        {
                            "id": "growclip",
                            "repository": "MichalMatu/growclip",
                            "agent_binding": BINDING,
                            "execution_enabled": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return home, registry, catalog

    def test_target_identity_comes_from_registry_catalog_and_remote_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home, registry, catalog = self._fixture(root)
            identity = inspect_operator_target(
                home=home,
                repository_id="growclip",
                registry_path=registry,
                catalog_path=catalog,
                branch_head_provider=lambda _control, branch: SHA if branch == "main" else "",
            )
            self.assertEqual(identity.repository_id, "growclip")
            self.assertEqual(identity.repository, "MichalMatu/growclip")
            self.assertEqual(identity.agent_binding, BINDING)
            self.assertEqual(identity.repository_ref, "main")
            self.assertEqual(identity.repository_commit_sha, SHA)

    def test_target_rejects_binding_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home, registry, catalog = self._fixture(root)
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["agents"][0]["agent_binding"] = "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "binding does not match"):
                resolve_operator_target(
                    home=home,
                    repository_id="growclip",
                    registry_path=registry,
                    catalog_path=catalog,
                )

    def test_target_rejects_execution_disabled_catalog_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home, registry, catalog = self._fixture(root)
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["agents"][0]["execution_enabled"] = False
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "execution-disabled"):
                resolve_operator_target(
                    home=home,
                    repository_id="growclip",
                    registry_path=registry,
                    catalog_path=catalog,
                )

    def test_target_rejects_origin_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home, registry, catalog = self._fixture(root)
            control = root / "growclip-control"
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(control),
                    "remote",
                    "set-url",
                    "origin",
                    "https://github.com/MichalMatu/shelly-link.git",
                ],
                check=True,
            )
            with self.assertRaisesRegex(RuntimeError, "origin does not match"):
                inspect_operator_target(
                    home=home,
                    repository_id="growclip",
                    registry_path=registry,
                    catalog_path=catalog,
                    branch_head_provider=lambda _control, _branch: SHA,
                )

    def test_target_rejects_noncanonical_remote_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home, registry, catalog = self._fixture(root)
            with self.assertRaisesRegex(RuntimeError, "canonical commit SHA"):
                inspect_operator_target(
                    home=home,
                    repository_id="growclip",
                    registry_path=registry,
                    catalog_path=catalog,
                    branch_head_provider=lambda _control, _branch: "not-a-sha",
                )


if __name__ == "__main__":
    unittest.main()
