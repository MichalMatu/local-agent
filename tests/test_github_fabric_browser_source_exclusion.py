"""Source-only browser import inventory; deliberately no old-client clearance."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_agent.conversation import github_fabric_browser_source_exclusion as guard

REPO_ROOT = Path(__file__).resolve().parents[1]


class BrowserSourceExclusionTests(unittest.TestCase):
    def test_checked_in_chrome_source_is_inventoried_but_never_cleared(self):
        result = guard.audit_browser_source_exclusion(REPO_ROOT)
        self.assertIn("service_worker.js", result.inspected_scripts)
        self.assertIn("worker_spawn.js", result.inspected_scripts)
        self.assertIn("content.js", result.inspected_scripts)
        self.assertIn("worker_github_fabric_intake.js", result.inspected_scripts)
        self.assertEqual(result.decision, "blocked_unattested_legacy_clients")
        self.assertFalse(result.browser_effects_permitted)
        self.assertFalse(result.old_offline_clients_excluded)
        self.assertFalse(result.independent_review_completed)
        self.assertEqual(len(result.inspected_scripts), len(set(result.inspected_scripts)))

    def test_bootstrap_requires_statically_enumerable_double_quoted_imports(self):
        self.assertEqual(
            guard._worker_imports('importScripts("worker_base.js", "worker_spawn.js");'),
            ("worker_base.js", "worker_spawn.js"),
        )
        bad = (
            'importScripts("worker_base.js", "worker_base.js");',
            "importScripts('github_fabric_private_parent_fence_reader.js');",
            'importScripts("worker_base.js" + injected);',
            'importScripts("worker_base.js"); importScripts("hidden.js");',
            'importScripts("worker_base.js"); chrome.tabs.create({});',
            'importScripts("../escape.js");',
        )
        for src in bad:
            with self.subTest(source=src):
                with self.assertRaisesRegex(ValueError, "bootstrap"):
                    guard._worker_imports(src)

    def test_indirect_loader_and_private_module_in_production_refused(self):
        for source in (
            'importScripts("github_fabric_private_parent_fence_reader.js");',
            'import("github_fabric_private_parent_fence_reader.js");',
            'const loader = import("other.js");',
            'eval("load runtime");',
            'new Function("unsafe")',
            'require("other.js")',
            'const x = "github_fabric_private_transport.js";',
        ):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    guard._script_safety("worker_events.js", source)

    def test_read_rejects_symlink_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "clean.js"
            source.write_text("const x = 1;", encoding="utf-8")
            self.assertEqual(guard._read_text(folder, "clean.js"), "const x = 1;")
            with self.assertRaises(ValueError):
                guard._read_text(folder, "../secret.js")
            (folder / "linked.js").symlink_to(source)
            with self.assertRaisesRegex(ValueError, "linked"):
                guard._read_text(folder, "linked.js")


    def test_real_recursive_closure_includes_secondary_worker_imports(self):
        observation = guard.audit_browser_source_exclusion(REPO_ROOT)
        self.assertIn("bridge_state.js", observation.inspected_scripts)
        self.assertIn("github_control_model.js", observation.inspected_scripts)
        self.assertIn("control_protocol.js", observation.inspected_scripts)
        self.assertFalse(observation.old_offline_clients_excluded)

    def test_injected_secondary_worker_loader_is_refused_end_to_end(self):
        original = guard._read_text

        def injected(directory, name):
            content = original(directory, name)
            if name == "worker_events.js":
                return content + '\\nimportScripts("unexpected.js");\\n'
            return content

        with mock.patch.object(guard, "_read_text", side_effect=injected):
            with self.assertRaisesRegex(ValueError, "Nested browser import graph"):
                guard.audit_browser_source_exclusion(REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
