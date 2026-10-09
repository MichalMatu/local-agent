"""Offline operator CLI: exact manifest bytes, rejection and pure task planning."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from local_agent.conversation import github_fabric_manual_handoff as handoff
from scripts import no_bridge_manual as cli
from tests.test_github_fabric_manual_new_parent import DEST, private_observation

HEAD = "a" * 40
BINDING = "2180d453-1357-4fbc-be1a-e1e5b8fbb10a"
BRANCH = "work/m8-no-bridge-operator-cli-20261009"


def invoke(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class NoBridgeOperatorCLITests(unittest.TestCase):
    def test_synthetic_manifest_export_import_offline(self):
        observation = private_observation()
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "synthetic.json"
            src.write_text(json.dumps(observation), encoding="utf-8")
            args = [
                "--pinned-source-sha", HEAD,
                "--destination-parent-url", DEST,
            ]
            status, manifest, errors = invoke(["export", "--input", str(src), *args])
            self.assertEqual(status, 0)
            self.assertEqual(errors, "")
            self.assertEqual(len(manifest.encode()), len(manifest))
            self.assertEqual(json.dumps(
                json.loads(manifest), ensure_ascii=False,
                sort_keys=True, separators=(",", ":"),
            ), manifest)
            self.assertIn('"manifest_digest"', manifest)
            self.assertNotIn("bootstrap_text", manifest)
            carried = Path(root) / "carried.json"
            carried.write_text(manifest, encoding="utf-8")
            code, review, errors = invoke(["inspect", "--input", str(carried), *args])
            self.assertEqual(code, 0)
            self.assertEqual(errors, "")
            self.assertEqual(json.loads(review)["decision"], "manual_read_only_review")
            self.assertEqual(handoff.import_manual_handoff(
                manifest, independently_pinned_source_sha=HEAD,
                expected_destination_parent_conversation_url=DEST,
            ).source_head_sha, HEAD)

    def test_invalid_source_and_credentials_never_echoed(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "private.json"
            path.write_text('{"secret":"VERY_PRIVATE_TOKEN"}')
            code, rendered, error = invoke([
                "export", "--input", str(path),
                "--pinned-source-sha", HEAD,
                "--destination-parent-url", DEST,
            ])
            self.assertEqual(code, 2)
            self.assertEqual(rendered, "")
            self.assertNotIn("VERY_PRIVATE_TOKEN", error)
            self.assertIn("refused", error)
            path.write_text("?" * (cli.MAX_INPUT_BYTES + 1))
            code, output, _error = invoke([
                "export", "--input", str(path),
                "--pinned-source-sha", HEAD,
                "--destination-parent-url", DEST,
            ])
            self.assertEqual(code, 2)
            self.assertEqual(output, "")

    def test_cli_task_plan_requires_manual_ack_and_has_no_side_effect(self):
        args = [
            "plan-test", "--job-id", "source-verification",
            "--source-sha", HEAD, "--work-branch", BRANCH,
            "--agent-binding", BINDING, "--profile", "core",
        ]
        code, output, stderr = invoke(args)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("refused", stderr)
        code, output, stderr = invoke([*args, "--acknowledge-review"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(output)
        self.assertEqual(payload["decision"], "manual_publication_review_only")
        self.assertFalse(payload["published"])
        self.assertFalse(payload["executing"])
        self.assertTrue(payload["binding_recheck_required"])
        self.assertEqual(payload["task"]["resources"], [])
        self.assertFalse(payload["task"]["allow_write"])
        self.assertIn(HEAD, payload["task"]["commands"][0])
        self.assertNotIn("pip install", payload["task"]["commands"][0])
        self.assertEqual(len(payload["task_digest"]), 64)

    def test_separate_isolated_setup_requires_an_explicit_flag(self):
        args = [
            "plan-test", "--job-id", "full-verification",
            "--source-sha", HEAD, "--work-branch", BRANCH,
            "--agent-binding", BINDING, "--profile", "full",
            "--acknowledge-review",
        ]
        exit_code, normal, _error = invoke(args)
        self.assertEqual(exit_code, 0)
        exit_code, isolated, _error = invoke([
            *args, "--approve-isolated-dependencies",
        ])
        self.assertEqual(exit_code, 0)
        first = json.loads(normal)
        second = json.loads(isolated)
        self.assertNotEqual(first["task"]["id"], second["task"]["id"])
        self.assertNotIn("pip install", first["task"]["commands"][0])
        self.assertIn("pip install", second["task"]["commands"][0])


if __name__ == "__main__":
    unittest.main()
