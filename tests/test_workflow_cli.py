from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from local_agent.cli import workflow
from local_agent.workflow import methods


FIXTURE = Path(__file__).parent / "fixtures" / "workflows" / "single_repo.json"


class WorkflowCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with mock.patch("sys.argv", ["workflow", *args]), redirect_stdout(output):
            code = workflow.main()
        return code, output.getvalue()

    def test_methods_lists_builtins_with_digest(self) -> None:
        code, output = self.run_cli("methods")
        self.assertEqual(code, 0)
        self.assertIn("deep-refactor\tversion=1\tsha256:", output)
        self.assertIn("cross-repo-api-change\tversion=1\tsha256:", output)
        self.assertIn("release-candidate\tversion=1\tsha256:", output)

    def test_method_prints_canonical_json(self) -> None:
        code, output = self.run_cli("method", "deep-refactor")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["name"], "deep-refactor")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["digest"], methods.method_digest(payload["spec"]))

    def test_validate_manifest_reports_digest(self) -> None:
        code, output = self.run_cli("validate-manifest", str(FIXTURE))
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["workflow_id"], "single-repo-build")
        self.assertRegex(payload["manifest_digest"], r"^sha256:[0-9a-f]{64}$")

    def test_validate_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"schema_version": 1}', encoding="utf-8")
            code, output = self.run_cli("validate-manifest", str(path))
        self.assertEqual(code, 2)
        payload = json.loads(output)
        self.assertFalse(payload["valid"])
        self.assertIn("workflow id", payload["error"])

    def test_local_submit_list_show_cancel_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prefix = ("--state-dir", directory)
            code, output = self.run_cli(*prefix, "submit", str(FIXTURE))
            self.assertEqual(code, 0)
            submitted = json.loads(output)
            self.assertEqual(submitted["workflow_id"], "single-repo-build")
            self.assertEqual(submitted["workflow_state"], "running")

            code, output = self.run_cli(*prefix, "list")
            self.assertEqual(code, 0)
            listing = json.loads(output)
            self.assertEqual(listing["workflow_ids"], ["single-repo-build"])

            code, output = self.run_cli(*prefix, "show", "single-repo-build")
            self.assertEqual(code, 0)
            shown = json.loads(output)
            self.assertEqual(shown["manifest"]["id"], "single-repo-build")
            self.assertEqual(shown["state"]["node_states"], {"build": "ready"})

            code, output = self.run_cli(*prefix, "cancel", "single-repo-build")
            self.assertEqual(code, 0)
            cancelled = json.loads(output)
            self.assertTrue(cancelled["cancel_requested"])
            self.assertEqual(cancelled["workflow_state"], "cancelled")

    def test_show_unknown_workflow_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_cli(
                "--state-dir",
                directory,
                "show",
                "missing",
            )
        self.assertEqual(code, 2)
        payload = json.loads(output)
        self.assertIn("unavailable", payload["error"])


if __name__ == "__main__":
    unittest.main()
