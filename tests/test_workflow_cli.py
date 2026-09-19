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
        fixture = (
            Path(__file__).parent
            / "fixtures"
            / "workflows"
            / "single_repo.json"
        )
        code, output = self.run_cli("validate-manifest", str(fixture))
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


if __name__ == "__main__":
    unittest.main()
