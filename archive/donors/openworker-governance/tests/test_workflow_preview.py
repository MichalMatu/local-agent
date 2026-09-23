from __future__ import annotations

import json
import unittest
from pathlib import Path

from local_agent.workflow import preview


FIXTURES = Path(__file__).parent / "fixtures" / "workflows"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class WorkflowPreviewTests(unittest.TestCase):
    def test_parallel_multi_repo_tasks_share_one_wave(self) -> None:
        result = preview.preview_workflow(load_fixture("parallel_multi_repo.json"))
        self.assertEqual(
            result.waves,
            (("backend", "android", "firmware"),),
        )
        self.assertEqual(result.final_state, "completed")
        self.assertEqual(result.waiting_nodes, ())

    def test_same_repository_ready_tasks_are_split_into_waves(self) -> None:
        manifest = {
            "schema_version": 1,
            "id": "same-repo-preview",
            "created_at": "2026-09-19T13:00:00Z",
            "nodes": [
                {
                    "id": "first",
                    "kind": "task",
                    "repository_id": "repo-a",
                    "agent_binding": "00000000-0000-4000-8000-000000000091",
                    "depends_on": [],
                    "task": {"resources": [], "commands": ["true"]},
                },
                {
                    "id": "second",
                    "kind": "task",
                    "repository_id": "repo-a",
                    "agent_binding": "00000000-0000-4000-8000-000000000091",
                    "depends_on": [],
                    "task": {"resources": [], "commands": ["true"]},
                },
            ],
        }
        result = preview.preview_workflow(manifest)
        self.assertEqual(result.waves, (("first",), ("second",)))
        self.assertEqual(result.final_state, "completed")

    def test_planner_checkpoint_stops_preview_after_dependencies(self) -> None:
        result = preview.preview_workflow(load_fixture("planner_checkpoint.json"))
        self.assertEqual(result.waves, (("audit",),))
        self.assertEqual(result.final_state, "waiting_planner")
        self.assertEqual(result.waiting_nodes, ("review",))

    def test_user_gate_stops_preview_after_dependencies(self) -> None:
        result = preview.preview_workflow(load_fixture("user_gate.json"))
        self.assertEqual(result.waves, (("audit",),))
        self.assertEqual(result.final_state, "waiting_user")
        self.assertEqual(result.waiting_nodes, ("choice",))

    def test_preview_does_not_mutate_manifest(self) -> None:
        manifest = load_fixture("parallel_multi_repo.json")
        original = json.dumps(manifest, sort_keys=True)
        preview.preview_workflow(manifest)
        self.assertEqual(json.dumps(manifest, sort_keys=True), original)


if __name__ == "__main__":
    unittest.main()
