"""GET-only pinned Git tree discovery of bounded task IDs and redacted results."""

from __future__ import annotations

import hashlib
import json
import unittest

from local_agent.conversation import github_fabric_agent_control_index as index
from tests.test_github_fabric_agent_control_recovery import (
    BINDING, BRANCH, CONTROL_SHA, SOURCE_SHA, TASK_ID, MemoryControlAPI,
)

PREFIX = "local-agent-m8-"
PENDING = "local-agent-m8-pending-test"


def _sha(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


class HistoryAPI(MemoryControlAPI):
    def __init__(self):
        super().__init__()
        self.truncated = False
        self.wrong_tree_identity = False
        self.include_task = True
        self.include_result = True
        self.include_pending = False
        self.duplicate_task = False
        self.wrong_tree_blob = False
        self.unexpected_path = False

    def request(self, method, path, body=None):
        if path == f"/git/trees/{'b' * 40}?recursive=1":
            self.operations.append((method, path, body))
            items = []
            if self.include_task:
                items.append({
                    "path": f".agent/tasks/{TASK_ID}.json",
                    "sha": "0" * 40 if self.wrong_tree_blob else _sha(self.task),
                    "type": "blob", "mode": "100644",
                })
            if self.include_result:
                items.append({
                    "path": f".agent/results/{TASK_ID}.json",
                    "sha": _sha(self.result), "type": "blob", "mode": "100644",
                })
            if self.include_pending:
                items.append({
                    "path": f".agent/tasks/{PENDING}.json",
                    "sha": "c" * 40, "type": "blob", "mode": "100644",
                })
            if self.duplicate_task:
                items.append(dict(items[0]))
            if self.unexpected_path:
                items.append({
                    "path": f".agent/tasks/{PREFIX}hidden.payload/private.txt",
                    "sha": "f" * 40, "type": "blob", "mode": "100644",
                })
            return {"sha": "c" * 40 if self.wrong_tree_identity else "b" * 40,
                    "truncated": self.truncated, "tree": items}
        return super().request(method, path, body)


class AgentControlHistoryTests(unittest.TestCase):
    def inspect(self, api, **overrides):
        kwargs = dict(
            task_id_prefix=PREFIX,
            independently_pinned_control_sha=CONTROL_SHA,
            independently_pinned_source_sha=SOURCE_SHA,
            expected_agent_binding=BINDING,
            expected_work_branch=BRANCH,
            enabled=True, api=api,
        )
        kwargs.update(overrides)
        return index.discover_agent_control_results(**kwargs)

    def test_completed_result_reconciled_to_exact_git_tree(self):
        api = HistoryAPI()
        history = self.inspect(api)
        self.assertEqual(len(history.result_observations), 1)
        self.assertEqual(history.result_observations[0].task_id, TASK_ID)
        self.assertEqual(history.result_observations[0].reported_outcome, "reported_pass_for_review")
        self.assertEqual(history.unconfirmed_task_ids, ())
        self.assertEqual(history.decision, "operator_review_only")
        self.assertFalse(history.can_dispatch)
        self.assertFalse(history.can_retry)
        self.assertFalse(history.can_authorize_browser_effect)
        self.assertTrue(all(item[0] == "GET" for item in api.operations))
        self.assertEqual(len(api.operations), 5)

    def test_missing_result_remains_unconfirmed_not_retried(self):
        api = HistoryAPI()
        api.include_pending = True
        report = self.inspect(api)
        self.assertEqual(report.unconfirmed_task_ids, (PENDING,))
        self.assertEqual(len(report.result_observations), 1)
        self.assertFalse(report.can_retry)

    def test_orphan_result_and_conflicting_paths_are_rejected(self):
        for mutation, expected in (
            ({"include_task": False}, "orphan result"),
            ({"duplicate_task": True}, "scoped Git entry"),
            ({"unexpected_path": True}, "unexpected scoped path"),
            ({"wrong_tree_blob": True}, "pinned Git tree"),
            ({"truncated": True}, "incomplete"),
            ({"wrong_tree_identity": True}, "incomplete"),
        ):
            api = HistoryAPI()
            for key, value in mutation.items():
                setattr(api, key, value)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, expected):
                self.inspect(api)

    def test_ineligible_result_fails_whole_discovery(self):
        api = HistoryAPI()
        api.result["task_digest"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "association"):
            self.inspect(api)

    def test_scoped_empty_returns_deny_only_review(self):
        api = HistoryAPI()
        api.include_task = False
        api.include_result = False
        found = self.inspect(api)
        self.assertEqual(found.result_observations, ())
        self.assertEqual(found.unconfirmed_task_ids, ())
        self.assertFalse(found.can_dispatch)
        self.assertEqual(len(api.operations), 2)

    def test_disabled_and_wrong_source_pins_deny_before_remote_read(self):
        for updates, error in (
            ({"enabled": False}, PermissionError),
            ({"task_id_prefix": "bad"}, ValueError),
            ({"independently_pinned_control_sha": "bad"}, ValueError),
            ({"independently_pinned_source_sha": "bad"}, ValueError),
            ({"expected_agent_binding": "bad"}, ValueError),
            ({"expected_work_branch": "main"}, ValueError),
            ({"token": "ambiguous token"}, ValueError),
        ):
            api = HistoryAPI()
            with self.subTest(updates=updates), self.assertRaises(error):
                self.inspect(api, **updates)
            self.assertEqual(api.operations, [])


if __name__ == "__main__":
    unittest.main()
