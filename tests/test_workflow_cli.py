from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from local_agent.cli import workflow
from local_agent.workflow import methods
from local_agent.workflow.store import WorkflowStore


FIXTURE = Path(__file__).parent / "fixtures" / "workflows" / "single_repo.json"
GATE_FIXTURE = Path(__file__).parent / "fixtures" / "workflows" / "user_gate.json"


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
        self.assertIn("cross-repo-api-change\tversion=2\tsha256:", output)
        self.assertIn("release-candidate\tversion=1\tsha256:", output)
        self.assertNotIn("cross-repo-api-change\tversion=1\t", output)

    def test_method_prints_canonical_json(self) -> None:
        code, output = self.run_cli("method", "deep-refactor")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["name"], "deep-refactor")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["digest"], methods.method_digest(payload["spec"]))

    def test_method_can_inspect_historical_version_while_defaulting_to_latest(self) -> None:
        code, output = self.run_cli("method", "cross-repo-api-change")
        self.assertEqual(code, 0)
        latest = json.loads(output)
        self.assertEqual(latest["version"], 2)

        code, output = self.run_cli(
            "method",
            "cross-repo-api-change",
            "--version",
            "1",
        )
        self.assertEqual(code, 0)
        historical = json.loads(output)
        self.assertEqual(historical["version"], 1)
        self.assertEqual(historical["spec"]["requirements"], {})
        self.assertEqual(
            historical["digest"],
            methods.method_digest(historical["spec"]),
        )

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

    def test_resolve_gate_records_exact_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prefix = ("--state-dir", directory)
            code, _output = self.run_cli(*prefix, "submit", str(GATE_FIXTURE))
            self.assertEqual(code, 0)
            store = WorkflowStore(Path(directory))
            store.set_node_state("user-gate", "audit", "succeeded")

            code, output = self.run_cli(
                *prefix,
                "resolve-gate",
                "user-gate",
                "choice",
                "preserve_compat",
                "--resolver",
                "cli-test",
            )
            self.assertEqual(code, 0)
            payload = json.loads(output)
            self.assertEqual(payload["decision"]["decision"], "preserve_compat")
            self.assertEqual(payload["decision"]["resolver"], "cli-test")
            self.assertEqual(payload["state"]["node_states"]["choice"], "succeeded")

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

    def test_run_cycle_uses_existing_registry_and_runs_exactly_one_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "repositories.json"
            registry.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "repositories": [
                            {
                                "id": "project-a",
                                "repository": "Example/project-a",
                                "agent_binding": "033327ab-700d-43b4-9b3b-caff1acaa2c7",
                                "control_dir": str(root / "control"),
                                "work_dir": str(root / "work"),
                                "checkpoints_dir": str(root / "checkpoints"),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            control_plane = object()
            cancellation_transport = object()
            cycle_result = SimpleNamespace(
                execution=SimpleNamespace(
                    published=("implement",),
                    reconciled=("audit",),
                    deferred_same_repository=(),
                    deferred_unrelated_work=(),
                    integrity_failures=(),
                ),
                cancellation=SimpleNamespace(
                    requested=("implement",),
                    deferred=(),
                    accepted=(),
                    completed=(),
                    rejected=(),
                    not_needed=(),
                ),
            )

            with mock.patch.object(
                workflow,
                "GitWorkflowControlPlane",
                return_value=control_plane,
            ) as control_class, mock.patch.object(
                workflow,
                "GitWorkflowCancellationTransport",
                return_value=cancellation_transport,
            ) as cancel_class, mock.patch.object(
                workflow,
                "run_lineage_cycle",
                return_value=cycle_result,
            ) as run_cycle:
                code, output = self.run_cli(
                    "--state-dir",
                    str(root / "state"),
                    "--registry",
                    str(registry),
                    "run-cycle",
                    "workflow-a",
                )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["workflow_id"], "workflow-a")
        self.assertEqual(payload["execution"]["published"], ["implement"])
        self.assertEqual(payload["execution"]["reconciled"], ["audit"])
        self.assertEqual(payload["cancellation"]["requested"], ["implement"])
        control_class.assert_called_once_with()
        cancel_class.assert_called_once_with(control_plane)
        run_cycle.assert_called_once()
        repositories = run_cycle.call_args.args[2]
        self.assertEqual(len(repositories), 1)
        self.assertEqual(repositories[0].repository_id, "project-a")
        self.assertEqual(
            repositories[0].agent_binding,
            "033327ab-700d-43b4-9b3b-caff1acaa2c7",
        )
        self.assertIs(run_cycle.call_args.args[3], control_plane)
        self.assertIs(run_cycle.call_args.args[4], cancellation_transport)

    def test_run_cycle_missing_explicit_registry_fails_before_git_transport(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = root / "missing-repositories.json"
            with mock.patch.object(workflow, "GitWorkflowControlPlane") as control_class:
                code, output = self.run_cli(
                    "--state-dir",
                    str(root / "state"),
                    "--registry",
                    str(missing),
                    "run-cycle",
                    "workflow-a",
                )

        self.assertEqual(code, 2)
        payload = json.loads(output)
        self.assertIn("explicit repository registry is unavailable", payload["error"])
        control_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
