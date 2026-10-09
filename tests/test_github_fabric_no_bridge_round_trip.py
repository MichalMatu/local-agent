"""End-to-end no-Bridge source plan -> pinned Git receipt -> review projection.

This uses no actual GitHub, browser, Local Agent execution or message sending.
"""

from __future__ import annotations

import base64
import hashlib
import json
import unittest

from local_agent.conversation import github_fabric_agent_control_index as history
from local_agent.conversation import github_fabric_no_bridge_task_plan as planner

HEAD = "a" * 40
CONTROL = "b" * 40
TREE = "c" * 40
BINDING = "2180d453-1357-4fbc-be1a-e1e5b8fbb10a"
BRANCH = "work/m8-no-bridge-task-planner-20261009"
PREFIX = "local-agent-nobridge-core-"


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _blob_sha(raw):
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


class PlanEvidenceAPI:
    def __init__(self, plan):
        self.task = json.loads(plan.task_json)
        self.result = {
            "id": plan.task_id, "work_branch": BRANCH,
            "task_digest": plan.task_digest,
            "allow_write": False, "mode": "commands",
            "status": "done", "edits": {}, "verification": [],
            "git_status": {"exit_code": 0, "output": ""},
            "git_diff": {"exit_code": 0, "output": ""},
            "stages": [{
                "outcome": "passed", "stage_phase": "commands",
                "stage_index": 1, "stage_total": 1,
            }],
            "commands": [{
                "command": self.task["commands"][0],
                "exit_code": 0, "timed_out": False, "idle_timed_out": False,
                "memory_limited": False, "background_process_leak": False,
                "output_truncated": False,
                "output": "PRIVATE LOG MUST NEVER LEAVE TEST FAKE",
            }],
        }
        self.include_result = True
        self.operations = []

    def request(self, method, path, body=None):
        self.operations.append((method, path, body))
        if method != "GET" or body is not None:
            raise AssertionError("No-Bridge fixture attempted a mutation")
        task_id = self.task["id"]
        if path == f"/git/commits/{CONTROL}":
            return {"sha": CONTROL, "tree": {"sha": TREE}}
        if path == f"/git/trees/{TREE}?recursive=1":
            entries = [{
                "path": f".agent/tasks/{task_id}.json",
                "type": "blob", "mode": "100644", "sha": _blob_sha(_bytes(self.task)),
            }]
            if self.include_result:
                entries.append({
                    "path": f".agent/results/{task_id}.json",
                    "type": "blob", "mode": "100644", "sha": _blob_sha(_bytes(self.result)),
                })
            return {"sha": TREE, "truncated": False, "tree": entries}
        known = {
            f"/contents/.agent/tasks/{task_id}.json?ref={CONTROL}": self.task,
            f"/contents/.agent/results/{task_id}.json?ref={CONTROL}": self.result,
        }
        if path not in known:
            raise AssertionError("Unexpected GitHub URI " + path)
        if not self.include_result and "results/" in path:
            raise AssertionError("Unconfirmed task should not fetch absent results")
        raw = _bytes(known[path])
        return {
            "type": "file", "encoding": "base64",
            "size": len(raw), "content": base64.b64encode(raw).decode(),
            "sha": _blob_sha(raw),
        }


class NoBridgePlanToHistoryTests(unittest.TestCase):
    def setUp(self):
        self.plan = planner.plan_no_bridge_source_test(
            task_job_id="source-verify", exact_source_sha=HEAD,
            work_branch=BRANCH, independently_verified_agent_binding=BINDING,
            operator_review_acknowledged=True,
        )
        self.api = PlanEvidenceAPI(self.plan)

    def discover(self):
        return history.discover_agent_control_results(
            task_id_prefix=PREFIX,
            independently_pinned_control_sha=CONTROL,
            independently_pinned_source_sha=HEAD,
            expected_agent_binding=BINDING,
            expected_work_branch=BRANCH,
            enabled=True, api=self.api,
        )

    def test_plan_and_report_recover_without_browser_or_raw_log(self):
        found = self.discover()
        self.assertEqual(len(found.result_observations), 1)
        child = found.result_observations[0]
        self.assertEqual(child.task_id, self.plan.task_id)
        self.assertEqual(child.task_digest, self.plan.task_digest)
        self.assertEqual(child.reported_outcome, "reported_pass_for_review")
        self.assertNotIn("PRIVATE LOG", repr(found))
        self.assertFalse(child.result_execution_attested)
        self.assertFalse(found.can_dispatch)
        self.assertFalse(found.can_retry)
        self.assertTrue(all(method == "GET" for method, *_ in self.api.operations))

    def test_truncated_but_successful_report_is_incomplete_not_failed(self):
        self.api.result["commands"][0]["output_truncated"] = True
        result = self.discover()
        self.assertEqual(len(result.result_observations), 1)
        observation = result.result_observations[0]
        self.assertEqual(
            observation.reported_outcome, "reported_incomplete_evidence_for_review"
        )
        self.assertEqual(observation.reported_status, "done")
        self.assertFalse(observation.automatic_retry_permitted)
        self.assertFalse(observation.effect_authorized)
        self.assertFalse(result.can_dispatch)
        self.assertFalse(result.can_retry)

    def test_missing_result_is_review_only_not_retry_authority(self):
        self.api.include_result = False
        found = self.discover()
        self.assertEqual(found.result_observations, ())
        self.assertEqual(found.unconfirmed_task_ids, (self.plan.task_id,))
        self.assertFalse(found.can_retry)
        self.assertEqual(len(self.api.operations), 3)

    def test_corrupt_report_or_tree_does_not_silently_pass(self):
        self.api.result["task_digest"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "association"):
            self.discover()
        self.api.result["task_digest"] = self.plan.task_digest
        self.api.result["commands"][0]["command"] = "echo forged command"
        with self.assertRaisesRegex(ValueError, "reported command"):
            self.discover()


if __name__ == "__main__":
    unittest.main()
