"""Source-only browser import inventory; deliberately no old-client clearance."""

from __future__ import annotations

import copy
import json
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
                return content + '\nimportScripts("unexpected.js");\n'
            return content

        with mock.patch.object(guard, "_read_text", side_effect=injected):
            with self.assertRaisesRegex(ValueError, "Nested browser import graph"):
                guard.audit_browser_source_exclusion(REPO_ROOT)


    def test_manifest_permission_scope_and_injection_mutations_fail_closed(self):
        original = json.loads(
            (REPO_ROOT / "chat_bridge" / "manifest.json").read_text(encoding="utf-8")
        )

        def add_script(manifest):
            manifest["content_scripts"][0]["js"].append("unreviewed.js")

        def widen_match(manifest):
            manifest["content_scripts"][0]["matches"].append("https://example.com/*")

        def change_world(manifest):
            manifest["content_scripts"][0]["world"] = "MAIN"

        def add_content_entry(manifest):
            manifest["content_scripts"].append(copy.deepcopy(manifest["content_scripts"][0]))

        changes = (
            ("debugger_permission", lambda m: m["permissions"].append("debugger")),
            ("widen_host", lambda m: m["host_permissions"].append("https://*/*")),
            ("widen_match", widen_match),
            ("new_script", add_script),
            ("new_content_entry", add_content_entry),
            ("main_world_injection", change_world),
            ("remote_access", lambda m: m.update({
                "externally_connectable": {"matches": ["https://example.com/*"]}
            })),
            ("optional_permissions", lambda m: m.update({
                "optional_permissions": ["debugger"]
            })),
            ("web_accessible_resources", lambda m: m.update({
                "web_accessible_resources": [{
                    "resources": ["unreviewed.js"], "matches": ["https://*/*"]
                }]
            })),
            ("background_type", lambda m: m["background"].update({"type": "module"})),
        )
        for name, change in changes:
            altered = copy.deepcopy(original)
            change(altered)
            with self.subTest(name=name):
                with mock.patch.object(guard.json, "loads", return_value=altered):
                    with self.assertRaisesRegex(ValueError, "manifest capability surface"):
                        guard.audit_browser_source_exclusion(REPO_ROOT)

    def test_manifest_duplicate_json_keys_are_rejected(self):
        original_read_text = Path.read_text

        def duplicated(path, *args, **kwargs):
            source = original_read_text(path, *args, **kwargs)
            if path.name == "manifest.json":
                return source.replace(
                    '"manifest_version": 3,',
                    '"manifest_version": 3, "manifest_version": 3,',
                    1,
                )
            return source

        with mock.patch.object(Path, "read_text", new=duplicated):
            with self.assertRaisesRegex(ValueError, "duplicate JSON keys"):
                guard.audit_browser_source_exclusion(REPO_ROOT)


    def test_extra_worker_import_refused_even_when_source_looks_harmless(self):
        original = guard._read_text

        def injected(directory, name):
            source = original(directory, name)
            if name == "service_worker.js":
                old = '  "worker_events.js"\n);'
                self.assertIn(old, source)
                return source.replace(
                    old, '  "worker_events.js",\n  "unreviewed_effect.js"\n);'
                )
            if name == "unreviewed_effect.js":
                return 'chrome.tabs.create({ url: "https://chatgpt.com/" });'
            return source

        with mock.patch.object(guard, "_read_text", side_effect=injected):
            with self.assertRaisesRegex(ValueError, "bootstrap import identity"):
                guard.audit_browser_source_exclusion(REPO_ROOT)

    def test_reordered_worker_imports_refused_for_same_source_set(self):
        original = guard._read_text

        def reordered(directory, name):
            source = original(directory, name)
            if name == "service_worker.js":
                first = '  "worker_state.js",\n  "worker_runtime.js",'
                second = '  "worker_runtime.js",\n  "worker_state.js",'
                self.assertIn(first, source)
                return source.replace(first, second)
            return source

        with mock.patch.object(guard, "_read_text", side_effect=reordered):
            with self.assertRaisesRegex(ValueError, "bootstrap import identity"):
                guard.audit_browser_source_exclusion(REPO_ROOT)

    def test_additional_static_nested_worker_import_refused(self):
        original = guard._read_text

        def nested(directory, name):
            source = original(directory, name)
            if name == "worker_base.js":
                old = '"github_control_model.js");'
                self.assertIn(old, source)
                return source.replace(
                    old, '"github_control_model.js", "unreviewed_effect.js");'
                )
            if name == "unreviewed_effect.js":
                return 'chrome.tabs.create({ url: "https://chatgpt.com/" });'
            return source

        with mock.patch.object(guard, "_read_text", side_effect=nested):
            with self.assertRaisesRegex(ValueError, "nested worker import identity"):
                guard.audit_browser_source_exclusion(REPO_ROOT)

    def test_reviewed_worker_import_baseline_is_exact(self):
        root = REPO_ROOT / "chat_bridge"
        self.assertEqual(
            guard._worker_imports(guard._read_text(root, "service_worker.js")),
            guard._WORKER_BOOTSTRAP,
        )
        self.assertEqual(
            guard._nested_worker_imports(guard._read_text(root, "worker_base.js")),
            guard._WORKER_NESTED_IMPORTS["worker_base.js"],
        )


if __name__ == "__main__":
    unittest.main()
