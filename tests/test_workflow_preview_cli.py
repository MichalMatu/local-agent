from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from local_agent.cli import workflow


FIXTURE = Path(__file__).parent / "fixtures" / "workflows" / "parallel_multi_repo.json"
CHECKPOINT_FIXTURE = (
    Path(__file__).parent / "fixtures" / "workflows" / "planner_checkpoint.json"
)


class WorkflowPreviewCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, dict]:
        output = io.StringIO()
        with mock.patch("sys.argv", ["workflow", *args]), redirect_stdout(output):
            code = workflow.main()
        return code, json.loads(output.getvalue())

    def test_preview_reports_parallel_wave_without_persistence(self) -> None:
        code, payload = self.run_cli("preview-manifest", str(FIXTURE))
        self.assertEqual(code, 0)
        self.assertEqual(payload["workflow_id"], "parallel-multi-repo")
        self.assertEqual(payload["waves"], [["backend", "android", "firmware"]])
        self.assertEqual(payload["final_state"], "completed")
        self.assertEqual(payload["waiting_nodes"], [])

    def test_preview_reports_planner_wait(self) -> None:
        code, payload = self.run_cli("preview-manifest", str(CHECKPOINT_FIXTURE))
        self.assertEqual(code, 0)
        self.assertEqual(payload["waves"], [["audit"]])
        self.assertEqual(payload["final_state"], "waiting_planner")
        self.assertEqual(payload["waiting_nodes"], ["review"])


if __name__ == "__main__":
    unittest.main()
