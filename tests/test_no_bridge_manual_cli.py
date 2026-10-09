"""Offline operator CLI: exact manifest bytes, rejection and pure task planning."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from local_agent.conversation import github_fabric_manual_handoff as handoff
from local_agent.conversation import github_fabric_agent_control_index as history
from local_agent.conversation import github_fabric_manual_new_parent as previewer
from scripts import no_bridge_manual as cli
from tests.test_github_fabric_manual_new_parent import DEST, private_observation
from tests.test_github_fabric_dispatch import admitted_children, operator_request

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

    def test_remote_verification_default_disabled_and_no_token_leak(self):
        params = [
            "verify-github",
            "--manifest", "missing-manifest.json",
            "--operator-request", "missing-source.json",
            "--child-requests", "missing-children.json",
            "--pinned-source-sha", HEAD,
            "--destination-parent-url", DEST,
        ]
        code, output, error = invoke(params)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("refused", error)
        with mock.patch.dict(os.environ, {}, clear=True):
            code, output, error = invoke([*params, "--allow-readonly-network"])
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertNotIn("missing-manifest.json", error)

    def test_explicit_github_verify_uses_env_token_and_redacted_view(self):
        observed = private_observation()
        preview = previewer.preview_manual_new_parent(
            observed, independently_pinned_source_sha=HEAD,
            destination_parent_conversation_url=DEST,
        )
        exported = handoff.export_manual_handoff(preview)
        with tempfile.TemporaryDirectory() as root:
            files = {}
            for name, value in (
                ("manifest", exported),
                ("operator", json.dumps(operator_request())),
                ("children", json.dumps(admitted_children())),
            ):
                path = Path(root) / (name + ".json")
                path.write_text(value, encoding="utf-8")
                files[name] = str(path)
            args = [
                "verify-github", "--manifest", files["manifest"],
                "--operator-request", files["operator"],
                "--child-requests", files["children"],
                "--pinned-source-sha", HEAD,
                "--destination-parent-url", DEST,
                "--allow-readonly-network",
            ]
            with mock.patch.dict(
                os.environ, {"LOCAL_AGENT_FABRIC_GITHUB_TOKEN": "PRIVATE_TEST_TOKEN"}
            ), mock.patch.object(
                handoff, "verify_manual_handoff_against_github",
                return_value=preview,
            ) as verifier:
                code, output, error = invoke(args)
                self.assertEqual(code, 0)
                self.assertEqual(error, "")
                self.assertNotIn("PRIVATE_TEST_TOKEN", output)
                self.assertEqual(json.loads(output)["decision"], "manual_read_only_review")
                self.assertFalse(json.loads(output)["browser_effects_permitted"])
                verifier.assert_called_once()
                kwargs = verifier.call_args.kwargs
                self.assertTrue(kwargs["enabled"])
                self.assertEqual(kwargs["token"], "PRIVATE_TEST_TOKEN")

    def test_status_github_opt_in_returns_only_redacted_review(self):
        args = [
            "status-github",
            "--task-id-prefix", "local-agent-m8-pr248",
            "--pinned-control-sha", "b" * 40,
            "--pinned-source-sha", HEAD,
            "--agent-binding", BINDING,
            "--work-branch", BRANCH,
        ]
        view = history.AgentControlReadOnlyHistory(
            control_commit_sha="b" * 40,
            source_commit_sha=HEAD,
            expected_work_branch=BRANCH,
            selected_task_prefix="local-agent-m8-pr248",
            result_observations=(),
            unconfirmed_task_ids=("local-agent-m8-pr248-test",),
        )
        code, output, error = invoke(args)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("refused", error)
        with mock.patch.dict(os.environ, {
            "LOCAL_AGENT_FABRIC_GITHUB_TOKEN": "CONFIDENTIAL_TOKEN"
        }), mock.patch.object(
            history, "discover_agent_control_results", return_value=view
        ) as finder:
            code, output, error = invoke([*args, "--allow-readonly-network"])
            self.assertEqual(code, 0)
            self.assertEqual(error, "")
            self.assertNotIn("CONFIDENTIAL_TOKEN", output)
            data = json.loads(output)
            self.assertEqual(data["decision"], "operator_review_only")
            self.assertFalse(data["can_dispatch"])
            self.assertFalse(data["can_retry"])
            self.assertFalse(data["can_authorize_browser_effect"])
            self.assertEqual(data["unconfirmed_task_ids"], ["local-agent-m8-pr248-test"])
            finder.assert_called_once()
            self.assertEqual(finder.call_args.kwargs["token"], "CONFIDENTIAL_TOKEN")
            self.assertTrue(finder.call_args.kwargs["enabled"])

    def test_status_github_missing_token_is_denied(self):
        args = [
            "status-github", "--task-id-prefix", "local-agent-m8-pr248",
            "--pinned-control-sha", "b" * 40,
            "--pinned-source-sha", HEAD,
            "--agent-binding", BINDING, "--work-branch", BRANCH,
            "--allow-readonly-network",
        ]
        with mock.patch.dict(os.environ, {}, clear=True):
            code, output, error = invoke(args)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertNotIn("token", error.lower())

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
