"""No-Bridge source verification task planning is offline, bounded and deny-only."""

from __future__ import annotations

import json
import unittest

from local_agent.conversation import github_fabric_agent_control_recovery as recovery
from local_agent.conversation import github_fabric_no_bridge_task_plan as planner
from local_agent.runtime import task_contract

SHA = "a" * 40
BINDING = "2180d453-1357-4fbc-be1a-e1e5b8fbb10a"
BRANCH = "work/m8-no-bridge-task-planner-20261009"


class NoBridgeTaskPlannerTests(unittest.TestCase):
    def plan(self, **updates):
        kwargs = dict(
            task_job_id="mac-verification",
            exact_source_sha=SHA,
            work_branch=BRANCH,
            independently_verified_agent_binding=BINDING,
            profile="core",
            operator_review_acknowledged=True,
        )
        kwargs.update(updates)
        return planner.plan_no_bridge_source_test(**kwargs)

    def test_disabled_default_refuses_plan(self):
        with self.assertRaisesRegex(PermissionError, "manual review"):
            planner.plan_no_bridge_source_test(
                task_job_id="test", exact_source_sha=SHA, work_branch=BRANCH,
                independently_verified_agent_binding=BINDING,
            )

    def test_approved_core_and_full_plans_remain_source_only(self):
        for profile in ("core", "full"):
            with self.subTest(profile=profile):
                planned = self.plan(profile=profile)
                task = json.loads(planned.task_json)
                self.assertEqual(task["id"], planned.task_id)
                self.assertEqual(task["work_branch"], BRANCH)
                self.assertEqual(task["agent_binding"], BINDING)
                self.assertEqual(task["resources"], [])
                self.assertFalse(task["allow_write"])
                self.assertEqual(task["dedupe_revision"], 1)
                self.assertEqual(planned.profile, profile)
                self.assertEqual(planned.decision, "manual_publication_review_only")
                self.assertFalse(planned.published)
                self.assertFalse(planned.executing)
                self.assertFalse(planned.automatic_retry_permitted)
                self.assertFalse(planned.browser_effects_permitted)
                self.assertTrue(planned.binding_recheck_required)
                self.assertEqual(planned.task_digest, task_contract.task_digest(task))
                task_contract.validate_task(task, require_agent_binding=True)
                self.assertNotIn("codex", task["commands"][0].lower())
                self.assertNotIn("chat_bridge", task["commands"][0])
                recovery._validate_scoped_task(
                    task, task_id=planned.task_id, source_sha=SHA,
                    binding=BINDING, work_branch=BRANCH,
                )

    def test_deterministic_same_plan_and_distinct_source_identity(self):
        same = self.plan()
        self.assertEqual(same, self.plan())
        different_sha = self.plan(exact_source_sha="b" * 40)
        different_branch = self.plan(work_branch="work/independent")
        different_job = self.plan(task_job_id="other-job")
        different_binding = self.plan(
            independently_verified_agent_binding="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        )
        for other in (different_sha, different_branch, different_job, different_binding):
            self.assertNotEqual(same.task_id, other.task_id)
            self.assertNotEqual(same.task_digest, other.task_digest)

    def test_invalid_job_or_source_or_binding_never_builds_a_task(self):
        for updates in (
            {"task_job_id": ""},
            {"task_job_id": "../malicious"},
            {"task_job_id": "space in name"},
            {"task_job_id": "x" * 90},
            {"exact_source_sha": "not-a-sha"},
            {"exact_source_sha": "Z" * 40},
            {"independently_verified_agent_binding": "not-a-binding"},
            {"work_branch": "main"},
            {"work_branch": "work/../main"},
            {"work_branch": "work/evil;rm"},
            {"work_branch": "work//double"},
            {"profile": "browser"},
            {"profile": "codex"},
            {"profile": True},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.plan(**updates)

    def test_no_ambient_authentication_in_plan(self):
        planned = self.plan()
        assert "https://" not in planned.task_json
        assert "Authorization" not in planned.task_json
        assert "token" not in planned.task_json.lower()
        task = json.loads(planned.task_json)
        self.assertEqual(len(task["commands"]), 1)
        self.assertTrue(task["commands"][0].startswith(
            'set -euo pipefail\n'
            f'test "$(git rev-parse HEAD)" = "{SHA}" || exit 3\n'
            'test -z "$(git status --porcelain)" || exit 4\n'
        ))


if __name__ == "__main__":
    unittest.main()
