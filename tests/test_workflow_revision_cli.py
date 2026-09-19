from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from local_agent.cli import workflow
from local_agent.workflow import contract


BINDING = "00000000-0000-4000-8000-0000000000b1"


def base_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": "revision-cli",
        "created_at": "2026-09-19T13:40:00Z",
        "nodes": [
            {
                "id": "audit",
                "kind": "task",
                "repository_id": "repo-a",
                "agent_binding": BINDING,
                "depends_on": [],
                "task": {
                    "work_branch": "main",
                    "allow_write": False,
                    "resources": [],
                    "commands": ["true"],
                },
            },
            {
                "id": "review",
                "kind": "planner_checkpoint",
                "depends_on": ["audit"],
            },
        ],
    }


def revision(base: dict) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": base["id"],
        "revision": 1,
        "created_at": "2026-09-19T13:41:00Z",
        "parent_digest": contract.manifest_digest(base),
        "checkpoint_node_id": "review",
        "nodes": [
            {
                "id": "implement",
                "kind": "task",
                "repository_id": "repo-a",
                "agent_binding": BINDING,
                "depends_on": ["review"],
                "task": {
                    "work_branch": "main",
                    "allow_write": False,
                    "resources": [],
                    "commands": ["true"],
                },
            }
        ],
    }


class WorkflowRevisionCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with mock.patch("sys.argv", ["workflow", *args]), redirect_stdout(output):
            code = workflow.main()
        return code, output.getvalue()

    def test_append_list_and_preview_effective_are_side_effect_free_for_repositories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / "state"
            base = base_manifest()
            rev = revision(base)
            base_path = root / "base.json"
            revision_path = root / "revision.json"
            base_path.write_text(json.dumps(base), encoding="utf-8")
            revision_path.write_text(json.dumps(rev), encoding="utf-8")
            prefix = ("--state-dir", str(state_dir))

            code, _ = self.run_cli(*prefix, "submit", str(base_path))
            self.assertEqual(code, 0)

            code, output = self.run_cli(
                *prefix,
                "append-revision",
                base["id"],
                str(revision_path),
            )
            self.assertEqual(code, 0)
            appended = json.loads(output)
            self.assertEqual(appended["revision_count"], 1)
            self.assertEqual(appended["revision"]["revision"], 1)
            self.assertRegex(appended["tip_digest"], r"^sha256:[0-9a-f]{64}$")

            code, output = self.run_cli(*prefix, "revisions", base["id"])
            self.assertEqual(code, 0)
            lineage = json.loads(output)
            self.assertEqual(lineage["workflow_id"], base["id"])
            self.assertEqual(lineage["revisions"][0]["node_ids"], ["implement"])

            code, output = self.run_cli(*prefix, "preview-effective", base["id"])
            self.assertEqual(code, 0)
            preview = json.loads(output)
            self.assertEqual(preview["revision_count"], 1)
            self.assertEqual(preview["node_count"], 3)
            self.assertEqual(preview["waves"], [["audit"]])
            self.assertEqual(preview["final_state"], "waiting_planner")
            self.assertEqual(preview["waiting_nodes"], ["review"])

            # Revision commands persist only under the isolated workflow state dir.
            # They must not create any repository control/work/checkpoint checkout.
            self.assertFalse((root / "repo-a").exists())


if __name__ == "__main__":
    unittest.main()
