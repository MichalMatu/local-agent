from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_agent.development.lab import (
    PROTECTED_OPERATIONAL_BRANCHES,
    build_dev_lab_layout,
    dev_lab_status,
    initialize_dev_lab,
    protected_production_paths,
)


class DevelopmentLabTests(unittest.TestCase):
    def test_default_layout_is_separate_and_synthetic_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            layout = build_dev_lab_layout(home=home)

            self.assertEqual(layout.checkout, home / "local-agent-dev")
            self.assertEqual(
                layout.root,
                home / "Library" / "Application Support" / "local-agent-dev",
            )
            self.assertEqual(layout.production_checkout, home / "local-agent")
            manifest = layout.manifest()
            self.assertEqual(manifest["mode"], "synthetic-only")
            self.assertEqual(
                manifest["protected_operational_branches"],
                list(PROTECTED_OPERATIONAL_BRANCHES),
            )
            self.assertEqual(
                manifest["capabilities"],
                {
                    "executor_enabled": False,
                    "remote_control_enabled": False,
                    "real_chrome_profile_enabled": False,
                    "native_host_registration_enabled": False,
                },
            )

    def test_initialize_creates_only_dev_namespace_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            layout = build_dev_lab_layout(home=home)
            first = initialize_dev_lab(layout)
            second = initialize_dev_lab(layout)

            self.assertEqual(first, second)
            self.assertTrue(layout.marker_path.is_file())
            self.assertEqual(
                json.loads(layout.marker_path.read_text(encoding="utf-8")),
                layout.manifest(),
            )
            for path in (
                layout.state_dir,
                layout.repositories_dir,
                layout.browser_profile_dir,
                layout.logs_dir,
                layout.fixtures_dir,
            ):
                self.assertTrue(path.is_dir())

            protected = protected_production_paths(
                home=home,
                production_checkout=layout.production_checkout,
            )
            self.assertFalse(protected["checkout"].exists())
            self.assertFalse(protected["state"].exists())
            self.assertFalse(protected["workspace"].exists())
            self.assertFalse(protected["launch_agent"].exists())
            self.assertFalse(protected["stdout_log"].exists())
            self.assertFalse(protected["stderr_log"].exists())
            self.assertFalse(protected["chrome_profile_root"].exists())

            status = dev_lab_status(layout)
            self.assertTrue(status["healthy"])
            self.assertEqual(status["problems"], [])

    def test_rejects_root_or_checkout_overlapping_production_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            protected = protected_production_paths(
                home=home,
                production_checkout=home / "local-agent",
            )
            bad_roots = (
                protected["state"],
                protected["state"] / "dev",
                protected["workspace"],
                protected["chrome_profile_root"] / "DevProfile",
                home / "Library" / "Application Support",
            )
            for root in bad_roots:
                with self.subTest(root=root):
                    with self.assertRaisesRegex(ValueError, "overlaps production"):
                        build_dev_lab_layout(home=home, root=root)

            with self.assertRaisesRegex(ValueError, "overlaps production"):
                build_dev_lab_layout(home=home, checkout=home / "local-agent")
            with self.assertRaisesRegex(ValueError, "overlaps production"):
                build_dev_lab_layout(home=home, checkout=home / "local-agent" / "dev")

    def test_rejects_dev_state_inside_checkout_or_checkout_inside_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with self.assertRaisesRegex(ValueError, "must be disjoint"):
                build_dev_lab_layout(
                    home=home,
                    root=home / "local-agent-dev" / "state",
                    checkout=home / "local-agent-dev",
                )
            with self.assertRaisesRegex(ValueError, "must be disjoint"):
                build_dev_lab_layout(
                    home=home,
                    root=home / "dev-lab",
                    checkout=home / "dev-lab" / "checkout",
                )

    def test_symlink_alias_to_production_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            production_state = home / "Library" / "Application Support" / "local-agent"
            production_state.mkdir(parents=True)
            alias = home / "dev-state-alias"
            alias.symlink_to(production_state, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "overlaps production"):
                build_dev_lab_layout(home=home, root=alias)

    def test_nonempty_unmarked_root_is_not_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            layout = build_dev_lab_layout(home=home)
            layout.root.mkdir(parents=True)
            (layout.root / "unexpected.txt").write_text("do not adopt", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "refusing to adopt"):
                initialize_dev_lab(layout)

    def test_existing_marker_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            layout = build_dev_lab_layout(home=home)
            initialize_dev_lab(layout)
            payload = layout.manifest()
            payload["capabilities"]["executor_enabled"] = True
            layout.marker_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "does not match"):
                initialize_dev_lab(layout)
            status = dev_lab_status(layout)
            self.assertFalse(status["healthy"])
            self.assertIn("marker_layout_mismatch", status["problems"])

    def test_initialize_rejects_symlinked_internal_directory_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            layout = build_dev_lab_layout(home=home)
            external = home / "external-state"
            external.mkdir()
            layout.root.mkdir(parents=True)
            layout.state_dir.symlink_to(external, target_is_directory=True)

            with self.assertRaisesRegex(RuntimeError, "directory must not be a symlink"):
                initialize_dev_lab(layout)

            self.assertEqual(tuple(external.iterdir()), ())
            self.assertFalse(layout.marker_path.exists())

    def test_initialize_rejects_symlinked_marker_without_overwriting_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            layout = build_dev_lab_layout(home=home)
            layout.root.mkdir(parents=True)
            external_marker = home / "external-marker.json"
            original = json.dumps(layout.manifest(), sort_keys=True)
            external_marker.write_text(original, encoding="utf-8")
            layout.marker_path.symlink_to(external_marker)

            with self.assertRaisesRegex(RuntimeError, "marker must not be a symlink"):
                initialize_dev_lab(layout)

            self.assertEqual(external_marker.read_text(encoding="utf-8"), original)

    def test_status_detects_missing_or_symlinked_lab_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            layout = build_dev_lab_layout(home=home)
            initialize_dev_lab(layout)
            layout.logs_dir.rmdir()

            status = dev_lab_status(layout)
            self.assertFalse(status["healthy"])
            self.assertIn("directory_missing_or_unsafe:logs", status["problems"])

            real_logs = layout.root / "real-logs"
            real_logs.mkdir()
            layout.logs_dir.symlink_to(real_logs, target_is_directory=True)
            status = dev_lab_status(layout)
            self.assertFalse(status["healthy"])
            self.assertIn("directory_missing_or_unsafe:logs", status["problems"])


if __name__ == "__main__":
    unittest.main()
