from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from local_agent.cli import workflow
from local_agent.workflow.store import WorkflowStore


FIXTURE = Path(__file__).parent / "fixtures" / "workflows" / "planner_checkpoint.json"


class WorkflowCheckpointCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, dict]:
        output = io.StringIO()
        with mock.patch("sys.argv", ["workflow", *args]), redirect_stdout(output):
            code = workflow.main()
        return code, json.loads(output.getvalue())

    def test_resolve_checkpoint_records_explicit_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prefix = ("--state-dir", directory)
            code, _payload = self.run_cli(*prefix, "submit", str(FIXTURE))
            self.assertEqual(code, 0)
            store = WorkflowStore(Path(directory))
            store.set_node_state("planner-checkpoint", "audit", "succeeded")

            code, payload = self.run_cli(
                *prefix,
                "resolve-checkpoint",
                "planner-checkpoint",
                "review",
                "--resolver",
                "planner-test",
                "--note",
                "Reviewed exact audit evidence.",
            )
            self.assertEqual(code, 0)
            self.assertEqual(payload["resolution"]["resolver"], "planner-test")
            self.assertEqual(
                payload["resolution"]["note"],
                "Reviewed exact audit evidence.",
            )
            self.assertEqual(payload["state"]["node_states"]["review"], "succeeded")
            self.assertEqual(payload["state"]["workflow_state"], "completed")


if __name__ == "__main__":
    unittest.main()
